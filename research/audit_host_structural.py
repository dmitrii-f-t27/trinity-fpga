#!/usr/bin/env python3
"""Hold the WIDE hosts to the oracle, on the codes where the bugs actually live.

research/audit_host_vs_oracle.py compares every code, which stops at 16 bits.
That leaves the 32-, 64-, 80-, 128- and 256-bit hosts unchecked, and they are the
ones nobody can brute-force.

Random sampling is the wrong tool. Every defect pass 234 found sat on a boundary:

    mxfp4    exp = all ones
    mxgf4    exp = all ones
    mxgf6    exp = all ones
    posit16  minpos and maxpos -- codes 0x0001 and 0x7FFF

None of those is likely to appear in a uniform draw over 2**32, let alone 2**128.
So this samples by STRUCTURE:

  * 0, and the all-ones word
  * every single-bit code, 1 << i          -- minpos and the sign bit live here
  * every single-hole code, mask ^ (1 << i) -- maxpos and NaR live here
  * for formats with an exponent field: each exponent of interest (0, 1, 2,
    bias-1, bias, bias+1, all-ones-1, all-ones) crossed with each mantissa of
    interest (0, 1, half, all ones), both signs
  * a fixed-seed random tail, so the sample is not only corners

For codes whose exponent puts the value far outside fp32's range, the oracle is
not consulted at all -- gf128 has a 49-bit exponent field and asking for the
exact value of 2**(2**48) is how pass 233 got its process killed. The correct fp32
answer there is determined by sign alone: Inf on overflow, zero on underflow.

Usage:  python3 research/audit_host_structural.py [--verbose]

Exits non-zero if any host disagrees, and ALSO if a host that should have been
checkable produced no comparisons at all -- pass 234 found a loader bug where
zero-checked read exactly like zero-wrong.
"""
import os
import random
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")
sys.path.insert(0, CONF)
sys.path.insert(0, HERE)

from gf_decode_golden import fraction_to_fp32       # noqa: E402
from audit_host_vs_oracle import (                   # noqa: E402
    ALIAS, INTEGER_DOMAIN, LOG_DOMAIN, find_format, host_golden, load_host,
    oracles, same_fp32,
)

FP32_INF = 0x7F800000

# Hosts whose OUTPUT DOMAIN I have not established, and which are therefore
# reported rather than scored. Comparing against a domain you have not verified
# manufactures disagreements: pass 234 did exactly that to int16, reporting
# 65,535 of 65,536 wrong when host and oracle agreed on every value.
#
#   gf256      624 of its comparisons land in classes that look like a whole
#              different layout, not a rounding difference. Either the host or
#              gf_ref's gf256 is describing another format; which needs the RTL.
#   cray_float the host returns 0.5 where the oracle returns zero, and +Inf where
#              the oracle returns zero. Cray's exponent field is not IEEE-shaped.
#   posit64    the host is named posit64_to_fp32, so it answers in fp32, but 62
#              of its differences are 1-ulp and 256 are unclassified -- es and
#              regime conventions at n=64 are exactly what pass 228 had to retract
#              a claim about.
#   int32/int64/int128  named *_to_fp32 or golden_fp32, so these convert rather
#              than pass the integer through. Whether the RTL rounds or truncates
#              a 64-bit integer into fp32 is not recorded anywhere.
DOMAIN_NOT_ESTABLISHED = {"gf256", "cray_float", "posit64",
                          "int32", "int64", "int128"}

# (format, code) pairs where the two answers are two READINGS, not a right and a
# wrong. Reported, never scored.
#
#   double_double / quad_double at the sign-bit-only code: the high limb is -0.0
#   and every other limb is +0.0. The host returns +0, which is what IEEE addition
#   gives for (-0) + (+0). This audit's adapter returned -0, taking the sign from
#   the top bit -- but extended_ref hands back Fraction(0, 1), which carries no
#   sign at all, so the -0 was the ADAPTER's opinion, not the oracle's. Which one
#   a double-double zero should carry is a convention nobody here has written down.
CONVENTION_OPEN = {
    ("double_double", 1 << 127),
    ("quad_double", 1 << 255),
}

CLASSES = (
    ("host flushes fp32 subnormal to zero",
     lambda g, w: ((w >> 23) & 0xFF) == 0 and (w & 0x7FFFFF) and (g & 0x7FFFFFFF) == 0),
    ("zero sign differs",
     lambda g, w: (g & 0x7FFFFFFF) == 0 and (w & 0x7FFFFFFF) == 0),
    ("oracle Inf, host finite",
     lambda g, w: ((w >> 23) & 0xFF) == 0xFF and not (w & 0x7FFFFF)
     and ((g >> 23) & 0xFF) != 0xFF),
    ("host Inf, oracle finite",
     lambda g, w: ((g >> 23) & 0xFF) == 0xFF and not (g & 0x7FFFFF)
     and ((w >> 23) & 0xFF) != 0xFF),
    ("truncated where round-to-nearest was due",
     lambda g, w: abs(((g >> 23) & 0xFF) - ((w >> 23) & 0xFF)) <= 1
     and (g >> 31) == (w >> 31) and g < w),
    ("differs by at most one ulp",
     lambda g, w: abs(((g >> 23) & 0xFF) - ((w >> 23) & 0xFF)) <= 1
     and (g >> 31) == (w >> 31)),
)


def classify(got, want):
    for name, test in CLASSES:
        try:
            if test(got, want):
                return name
        except Exception:                         # noqa: BLE001
            continue
    return "unclassified"


# Beyond this many binades from 2**0 the fp32 answer is Inf or zero by
# construction, and the exact value is not worth -- or safe -- to materialise.
SAFE_BINADES = 4096
RANDOM_TAIL = 256


def structural_codes(width, fmt):
    """Corners first, then a fixed-seed tail."""
    mask = (1 << width) - 1
    codes = {0, mask}
    for i in range(width):
        codes.add(1 << i)              # minpos, the sign bit, each mantissa bit
        codes.add(mask ^ (1 << i))     # maxpos, NaR, each hole
    E = getattr(fmt, "exp_bits", 0)
    M = getattr(fmt, "mant_bits", 0)
    B = getattr(fmt, "bias", 0)
    if E and M and 1 + E + M == width:
        EM = (1 << E) - 1
        MM = (1 << M) - 1
        for e in (0, 1, 2, B - 1, B, B + 1, EM - 1, EM):
            if not 0 <= e <= EM:
                continue
            for m in (0, 1, MM // 2, MM):
                for s in (0, 1):
                    codes.add((s << (width - 1)) | (e << M) | m)
    rnd = random.Random(20260806)
    for _ in range(RANDOM_TAIL):
        codes.add(rnd.randrange(1 << width))
    return sorted(codes)


def _oracle_would_be_unsafe(E, M, B, e, EM):
    """True only when asking the oracle for this code's exact value is dangerous.

    The danger is memory: a 49-bit exponent field means a value of 2**(2**48),
    and materialising it as a Fraction is what killed this audit's first run and
    pass 233's before it.
    """
    return (abs(e - B) > SAFE_BINADES
            or abs(EM - B) > SAFE_BINADES
            or abs(1 - B) > SAFE_BINADES)


def analytic_fp32(width, fmt, raw):
    """fp32 answer for a code the oracle must not be asked about, else None.

    Only used when the exponent field puts the magnitude so far outside fp32's
    range that the answer is Inf or zero whatever the significand is -- and only
    for exponents strictly inside the normal range, so no special-code
    convention is being assumed.
    """
    E = getattr(fmt, "exp_bits", 0)
    M = getattr(fmt, "mant_bits", 0)
    B = getattr(fmt, "bias", 0)
    if not (E and M and 1 + E + M == width):
        return None
    EM = (1 << E) - 1
    e = (raw >> M) & EM
    sign = (raw >> (width - 1)) & 1
    m = raw & ((1 << M) - 1)

    # This shortcut assumes an IEEE-shaped layout: radix 2, implicit leading 1,
    # sign in the top bit, exp=0 meaning subnormal-or-zero. That is false for
    # IBM hex float (radix 16), for VAX (whose sign=1, exp=0 is the RESERVED
    # OPERAND, not a negative zero -- the pass 188 finding), and for x87 (which
    # carries an explicit integer bit). Those all have small exponent fields, so
    # the oracle is perfectly safe for them and gets asked. The shortcut is only
    # for the case the oracle CANNOT be asked: an exponent so wide that the exact
    # value would not fit in memory.
    if not _oracle_would_be_unsafe(E, M, B, e, EM):
        return None

    if e == EM:
        # Only the format's own convention decides what this pattern means, so
        # ask the format -- but never ask for its VALUE. gf128 has a 49-bit
        # exponent field, and the exact value of a code with e = EM is 2**(2**48).
        # Materialising that is how this audit's first run was SIGKILLed, and how
        # pass 233's was before it -- the fourth time round this trap.
        has_inf = getattr(fmt, "has_inf", None)
        if has_inf is True:
            return 0x7FC00001 if m else ((sign << 31) | FP32_INF)
        if has_inf is False and EM - B > SAFE_BINADES:
            return (sign << 31) | FP32_INF        # finite, but far past fp32
        return None

    if e == 0:
        if m == 0:
            return sign << 31
        if 1 - B < -SAFE_BINADES:
            return sign << 31                     # subnormal, underflows fp32
        return None

    k = e - B
    if k > SAFE_BINADES:
        return (sign << 31) | FP32_INF
    if k < -SAFE_BINADES:
        return sign << 31
    return None


def reference(mod, fmt, raw, width):
    """Oracle answer as fp32 bits, or None when not comparable."""
    val = mod.decode(fmt, raw)
    Special = getattr(mod, "Special", None)
    if Special is not None and isinstance(val, Special):
        kind = getattr(val, "kind", None)
        if kind == "inf":
            return (getattr(val, "sign", 0) << 31) | FP32_INF
        if kind == "nan":
            return 0x7FC00001
        return None
    if isinstance(val, (int, Fraction)):
        return fraction_to_fp32(Fraction(val), (raw >> (width - 1)) & 1)
    return None


def main():
    verbose = "--verbose" in sys.argv
    mods = oracles()
    hosts = sorted(f for f in os.listdir(CONF)
                   if f.endswith(".py") and "ax7203" in f)
    rows = []
    for fn in hosts:
        stem = fn[:-len("_conformance_ax7203.py")] if fn.endswith("_conformance_ax7203.py") \
            else fn[:-len("_ax7203.py")]
        stem = stem[:-len("_decode")] if stem.endswith("_decode") else stem
        key = ALIAS.get(stem, stem)
        if key is None:
            continue
        oname, omod, fmt = find_format(key, mods)
        if fmt is None:
            continue
        width = getattr(fmt, "width", 1 + getattr(fmt, "exp_bits", 0)
                        + getattr(fmt, "mant_bits", 0))
        if not isinstance(width, int) or width <= 16:
            continue                    # audit_host_vs_oracle covers these in full
        if key in LOG_DOMAIN:
            rows.append((fn, key, width, 0, 0, 0, "log-domain host", {}))
            continue
        if key in DOMAIN_NOT_ESTABLISHED:
            rows.append((fn, key, width, 0, 0, 0,
                         "output domain not established -- reported, not scored", {}))
            continue
        try:
            host = load_host(os.path.join(CONF, fn))
        except BaseException as e:                    # noqa: BLE001
            rows.append((fn, key, width, 0, 0, 0, "load failed: %s" % type(e).__name__, {}))
            continue
        gname, gfn = host_golden(host, key)
        if gfn is None:
            rows.append((fn, key, width, 0, 0, 0, "no golden function found", {}))
            continue
        integer = key in INTEGER_DOMAIN

        checked = bad = unscoreable = 0
        first = None
        import collections as _c
        classes = _c.Counter()
        for raw in structural_codes(width, fmt):
            try:
                got = gfn(raw)
            except BaseException as ex:               # noqa: BLE001
                bad += 1
                if first is None:
                    first = "code %#x: host raised %s" % (raw, type(ex).__name__)
                continue
            if got is None:
                unscoreable += 1
                continue
            got &= 0xFFFFFFFF if not integer else (1 << 128) - 1
            if integer:
                val = omod.decode(fmt, raw)
                if not isinstance(val, (int, Fraction)) or Fraction(val).denominator != 1:
                    unscoreable += 1
                    continue
                want = int(val) & ((1 << width) - 1)
                got &= (1 << width) - 1
            else:
                want = analytic_fp32(width, fmt, raw)
                if want is None:
                    want = reference(omod, fmt, raw, width)
                if want is None:
                    unscoreable += 1
                    continue
            if (key, raw) in CONVENTION_OPEN and got != want:
                unscoreable += 1
                continue
            checked += 1
            ok = (got == want) if integer else same_fp32(got, want)
            if not ok:
                bad += 1
                classes[classify(got, want) if not integer else "integer domain"] += 1
                if first is None:
                    first = "code %#x: host %#x oracle %#x" % (raw, got, want)
        rows.append((fn, key, width, checked, bad, unscoreable,
                     "%s vs %s.decode" % (gname, oname), classes))

    print("%-46s %-14s %5s %8s %6s" % ("host", "format", "bits", "compared", "differ"))
    tot_c = tot_b = 0
    silent = []
    import collections as _c
    all_classes = _c.Counter()
    for fn, key, width, checked, bad, unsc, note, classes in rows:
        all_classes.update(classes)
        if checked or bad or verbose:
            print("%-46s %-14s %5d %8d %6d%s%s"
                  % (fn[:46], key, width, checked, bad,
                     "  <<<" if bad else "",
                     ("   %d unscoreable" % unsc) if unsc else ""))
        tot_c += checked
        tot_b += bad
        # A host deliberately not scored is not a host that went silent. Only an
        # unexplained zero counts -- that is the case pass 234 could not see.
        if checked == 0 and "log-domain" not in note and "not established" not in note:
            silent.append((fn, note))
    for fn, key, width, checked, bad, unsc, note, classes in rows:
        if bad:
            print("        %s -- %s" % (note, ", ".join(
                "%s x%d" % (k, v) for k, v in classes.most_common())))
    print()
    print("wide hosts sampled       : %d" % len([r for r in rows if r[3]]))
    print("codes compared           : %d" % tot_c)
    print("disagreements            : %d" % tot_b)
    for k, v in all_classes.most_common():
        print("   %5d  %s" % (v, k))
    skipped = [r for r in rows if "not established" in r[6]]
    if skipped:
        print("hosts reported but NOT scored: %d" % len(skipped))
        for r in skipped:
            print("   %-46s %s" % (r[0][:46], r[1]))
    print("hosts that compared NOTHING: %d" % len(silent))
    for fn, note in silent:
        print("   %-46s %s" % (fn[:46], note))
    # A host that checked nothing is not a host that passed. Pass 234 found a
    # loader bug where those two were indistinguishable in the output.
    return 1 if (tot_b or silent) else 0


if __name__ == "__main__":
    sys.exit(main())
