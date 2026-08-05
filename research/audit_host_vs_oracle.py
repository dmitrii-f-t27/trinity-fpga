#!/usr/bin/env python3
"""Does each hardware host's golden agree with the oracle for its format?

Pass 233 checked the 14 decode hosts that declare `N,E,M,BIAS` and found four
that could not finish a run. That left the rest: 35 hosts whose golden is a
literal table or a hand-written model, and which nothing has ever compared
against the oracle that the conformance packs are built on.

A decode host answers "what fp32 should the board return for this code". So does
the oracle, once its exact Fraction is rounded to fp32 -- and that rounding is
conformance/gf_decode_golden.fraction_to_fp32, which agrees with gf_ref.decode on
all 1,135,952 codes of gf4 through gf20.

For every format narrow enough, this compares the two on EVERY code.

Comparison rules, and why they are not just `==`:

  * NaN payload. IEEE 754 does not mandate one. Hosts canonicalise to
    0x7FC00001; anything with exp=0xFF and a nonzero mantissa is the same
    answer, so NaN is compared by class.
  * Signed zero is NOT waived. -0 and +0 are different codes and a decode host
    that loses the sign is wrong.
  * Inf sign is compared exactly.

Usage:  python3 research/audit_host_vs_oracle.py [--verbose]
"""
import glob
import importlib
import os
import sys
import types
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")
sys.path.insert(0, CONF)

from gf_decode_golden import fraction_to_fp32   # noqa: E402

FP32_INF = 0x7F800000

# host filename stem -> oracle format key, where they differ
ALIAS = {
    "posit8_es2": "posit8",
    "mxfp8_e4m3": "mxfp8_e4m3",
    # The host named mxfp6 declares N,E,M,BIAS = 6,3,2,3 -- that is FP6 E3M2.
    # mxfp_ref's "mxfp6" is E2M3 (exp_bits=2, mant_bits=3, bias=1). OCP MX v1.0
    # defines BOTH, and issue #199 records fp6_e2m3 and fp6_e3m2 as separate
    # Tier-E cells, so the collision is in this one filename: it claims the
    # family name for one of the two variants. Compared against the variant it
    # actually implements, which fp8_ref carries as fp6_e3m2.
    "mxfp6": "fp6_e3m2",
    "gf_generic": None,          # multi-format wrapper, no single format
    "gf_wide": None,
    "ternary_mac": None,
    "trinet_mac32": None,
    "bram_test": None,
    "top": None,
    "any_format": None,
}

GOLDEN_NAMES = ("golden", "decode", "expected", "golden_value", "ref_decode")


def oracles():
    mods = {}
    for path in sorted(glob.glob(os.path.join(CONF, "*_ref.py"))):
        name = os.path.basename(path)[:-3]
        try:
            mods[name] = importlib.import_module(name)
        except Exception:                         # noqa: BLE001
            continue
    return mods


def find_format(key, mods):
    for name, mod in mods.items():
        f = getattr(mod, "FORMATS", {}).get(key)
        if f is not None:
            return name, mod, f
    return None, None, None


def load_host(path):
    src = open(path, encoding="utf-8", errors="replace").read()
    sys.modules.setdefault("serial", types.ModuleType("serial"))
    mod = types.ModuleType("host_under_audit")
    mod.__dict__["__name__"] = "host_under_audit"
    mod.__dict__["__file__"] = path   # hosts resolve their own directory from this
    exec(compile(src, path, "exec"), mod.__dict__)      # noqa: S102
    return mod


def host_golden(mod, key):
    for base in GOLDEN_NAMES:
        for cand in (base + "_" + key, base):
            fn = getattr(mod, cand, None)
            if callable(fn):
                return cand, fn
    # some hosts name it after the format alone
    fn = getattr(mod, key, None)
    return (key, fn) if callable(fn) else (None, None)


def same_fp32(a, b):
    """Equal as an fp32 answer -- NaN by class, everything else exactly."""
    if a == b:
        return True
    a_nan = (a >> 23) & 0xFF == 0xFF and (a & 0x7FFFFF)
    b_nan = (b >> 23) & 0xFF == 0xFF and (b & 0x7FFFFF)
    return bool(a_nan and b_nan)


# Not every host answers in fp32. An integer-format host returns the integer the
# board returns, and comparing that against the fp32 ENCODING of the same number
# is comparing two different questions -- the first version of this did exactly
# that and reported int16 as 65535 disagreements out of 65536, when the host and
# the oracle agree on every value.
#
# lns hosts answer in the log domain for the same reason.
INTEGER_DOMAIN = {"bcd", "int4", "int8", "int16", "int32", "int64", "int128",
                  "uint4", "uint8", "uint16", "uint32"}
LOG_DOMAIN = {"lns8", "lns16", "lns32", "lns64"}


def reference(mod, fmt, raw, sign_bit):
    """The oracle's answer as fp32 bits, or None when it is not comparable."""
    val = mod.decode(fmt, raw)
    Special = getattr(mod, "Special", None)
    if Special is not None and isinstance(val, Special):
        kind = getattr(val, "kind", None)
        if kind == "inf":
            return (getattr(val, "sign", 0) << 31) | FP32_INF
        if kind == "nan":
            return 0x7FC00001
        return None                       # nar / exp / anything else: not an fp32
    if isinstance(val, Fraction) or isinstance(val, int):
        return fraction_to_fp32(Fraction(val), sign_bit)
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
            rows.append((fn, "-", "multi-format or non-format wrapper", 0, 0, None))
            continue
        oname, omod, fmt = find_format(key, mods)
        if fmt is None:
            rows.append((fn, key, "no oracle has this format", 0, 0, None))
            continue
        width = 1 + getattr(fmt, "exp_bits", 0) + getattr(fmt, "mant_bits", 0)
        width = getattr(fmt, "width", width)
        if not isinstance(width, int) or width <= 0 or width > 16:
            rows.append((fn, key, "width %s -- not exhaustively checkable here" % width,
                         0, 0, None))
            continue
        try:
            host = load_host(os.path.join(CONF, fn))
        except BaseException as e:                # noqa: BLE001
            rows.append((fn, key, "load failed: %s" % type(e).__name__, 0, 0, None))
            continue
        gname, gfn = host_golden(host, key)
        if gfn is None:
            rows.append((fn, key, "no golden function found", 0, 0, None))
            continue

        if key in LOG_DOMAIN:
            rows.append((fn, key, "log-domain host -- answers in log, not fp32",
                         0, 0, None))
            continue
        integer = key in INTEGER_DOMAIN

        bad = checked = skipped = unscoreable = 0
        first = None
        for raw in range(1 << width):
            try:
                raw_got = gfn(raw)
            except BaseException:                 # noqa: BLE001
                bad += 1
                if first is None:
                    first = "code %#x: host raised" % raw
                continue
            if raw_got is None:
                # Not a wrong answer -- NO answer. bcd's golden returns None for
                # any nibble above 9, so the host cannot score the board on 156 of
                # 256 codes. Counting that as a disagreement would be claiming the
                # oracle is right about something the host never asserted.
                unscoreable += 1
                continue
            got = raw_got & 0xFFFFFFFF
            if integer:
                val = omod.decode(fmt, raw)
                if not isinstance(val, (int, Fraction)) or Fraction(val).denominator != 1:
                    skipped += 1
                    continue
                want = int(val) & 0xFFFFFFFF     # two's complement, host's word width
            else:
                want = reference(omod, fmt, raw, (raw >> (width - 1)) & 1)
                if want is None:
                    skipped += 1
                    continue
            checked += 1
            ok = (got == want) if integer else same_fp32(got, want)
            if not ok:
                bad += 1
                if first is None:
                    first = ("code %#x: host %#010x oracle %#010x" % (raw, got, want))
        rows.append((fn, key, "%s vs %s.decode%s"
                     % (gname, oname, " (integer domain)" if integer else ""),
                     checked, bad, first, unscoreable))

    print("%-48s %-12s %8s %6s" % ("host", "format", "compared", "differ"))
    compared = tot_bad = ran = 0
    for row in rows:
        fn, key, note, checked, bad, first = row[:6]
        unscoreable = row[6] if len(row) > 6 else 0
        if checked or bad or unscoreable:
            ran += 1
            compared += checked
            tot_bad += bad
            print("%-48s %-12s %8d %6d%s%s"
                  % (fn[:48], key, checked, bad, "  <<<" if bad else "",
                     ("   %d codes the host cannot score" % unscoreable)
                     if unscoreable else ""))
            if first:
                print("        first: %s" % first)
        elif verbose:
            print("%-48s %-12s   %s" % (fn[:48], key, note))
    print()
    print("hosts exhaustively compared : %d of %d" % (ran, len(hosts)))
    print("codes compared              : %d" % compared)
    print("disagreements               : %d" % tot_bad)
    print("codes the hosts cannot score: %d"
          % sum((r[6] if len(r) > 6 else 0) for r in rows))
    if not verbose:
        print("(re-run with --verbose to see the hosts that were not comparable)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
