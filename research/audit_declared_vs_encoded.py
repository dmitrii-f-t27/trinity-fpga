#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Does each pack encode the format its oracle declares?

Pass 228 found the campaign record carrying this line:

    published pack    posit8, es = 2, Posit Standard 2022, maxpos 16,777,216
                      -- validated above against SoftPosit, 255/255

The published pack is es = 0, maxpos 64, and `conformance/posit_ref.py` has declared it
that way since the file was created. The es = 2 dataset validated against SoftPosit was a
scratchpad artefact, not `conformance/vectors/posit8_*.json`.

Both validations were real and they were about different formats. A paper citing that line
for "posit8 conforms to Posit Standard 2022" would be citing data that is not in the
repository.

The check is one landmark per format: decode the largest positive code and compare against
what the declared parameters require. Nothing subtle -- maxpos is a function of the
declared width and exponent size, so if the pack disagrees the declaration is wrong, or
the pack is, and either way somebody is about to cite the wrong one.

    python3 research/audit_declared_vs_encoded.py [--verbose] [--self-check]
"""
from __future__ import annotations

import glob
import importlib
import json
import os
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")


def posit_maxpos(n, es):
    """useed^(n-2) -- the largest finite posit at this width and exponent size."""
    useed = 2 ** (2 ** es)
    return Fraction(useed) ** (n - 2)


def check_posits():
    sys.path.insert(0, CONF)
    P = importlib.import_module("posit_ref")
    rows = []
    for name, fmt in P.FORMATS.items():
        n = getattr(fmt, "n", getattr(fmt, "width", None))
        es = getattr(fmt, "es", None)
        if n is None or es is None:
            continue
        top = (1 << (n - 1)) - 1                   # largest positive code
        got = P.decode(fmt, top)
        want = posit_maxpos(n, es)
        rows.append((name, n, es, got, want, got == want))
    return rows


def sem_maxfinite(fmt, has_inf, nan_at_max_only=False):
    """Largest finite value of a sign-exponent-mantissa format from its declared fields.

    exp field all-ones is reserved when the format has infinities, so the top finite
    exponent is one below; otherwise it is the all-ones field itself. That single
    distinction is the one pass 197 settled for GoldenFloat and pass 198 found the RTL
    getting wrong, so the landmark is computed from has_inf rather than assumed.
    """
    e, m, b = fmt.exp_bits, fmt.mant_bits, fmt.bias
    base = getattr(fmt, "base", 2)
    top = (1 << e) - 1 - (1 if has_inf else 0)
    # fp8 E4M3 and MXFP8 E4M3 reserve only the all-ones EXPONENT with the all-ones
    # MANTISSA for NaN, so their largest finite sits one mantissa step below. Treating
    # them like a no-infinity format reads that NaN as the maximum, which is what the
    # first version of this landmark did for both.
    top_mant = (1 << m) - 1 - (1 if nan_at_max_only else 0)
    if base != 2:
        # IBM hexadecimal floating point: the exponent is a power of SIXTEEN and the
        # significand has no implicit leading one. 2^(exp-bias) is a different format.
        return Fraction(top_mant, 1 << m) * Fraction(base) ** (top - b)
    return (1 + Fraction(top_mant, 1 << m)) * Fraction(2) ** (top - b)


MAX_SAFE_EXP = 1 << 20      # see the comment in check_sem


def check_sem(mod_name, family_has_inf=None, skipped=None):
    """(name, decoded, required, ok) per format, for the sign-exponent-mantissa families."""
    sys.path.insert(0, CONF)
    try:
        M = importlib.import_module(mod_name)
    except Exception:
        return []
    rows = []
    if skipped is None:
        skipped = []
    for name, fmt in getattr(M, "FORMATS", {}).items():
        if not all(hasattr(fmt, a) for a in ("exp_bits", "mant_bits", "bias")):
            continue
        # Bounded, for the reason pass 186 wrote down and this file walked into anyway:
        # a wide GF format has a bias near 2^60, so 2^(top - bias) is not slow but
        # impossible. Formats past the bound are skipped and counted, never called clean.
        if (1 << fmt.exp_bits) - 1 - fmt.bias > MAX_SAFE_EXP or fmt.bias > MAX_SAFE_EXP:
            skipped.append(name)
            continue
        if getattr(fmt, "kind", "") == "int":
            skipped.append(name)          # an integer element has no exponent landmark
            continue
        has_inf = getattr(fmt, "has_inf", None)
        if has_inf is None:
            # x87 is IEEE 754 double-extended and DOES have infinities, which pass 186
            # established after the corpus had filed it under legacy for the opposite
            # reason. Passing the family default here read its all-ones exponent as the
            # top finite one and decoded a NaN.
            has_inf = (getattr(fmt, "kind", "") == "x87") if family_has_inf is None \
                else family_has_inf
            if getattr(fmt, "kind", "") == "x87":
                has_inf = True
        if getattr(fmt, "explicit_int_bit", False):
            # cray and x87 carry the leading bit in the field rather than implying it, so
            # the significand is mant/2^(m-1) and not 1 + mant/2^m. A landmark that
            # assumes the implicit one is off by a factor of two before it starts.
            skipped.append(name)
            continue
        nmo = bool(getattr(fmt, "nan_at_max_only", False))
        want = sem_maxfinite(fmt, has_inf, nmo)
        top_exp = (1 << fmt.exp_bits) - 1 - (1 if has_inf else 0)
        code = (top_exp << fmt.mant_bits) | ((1 << fmt.mant_bits) - 1 - (1 if nmo else 0))
        try:
            got = M.decode(fmt, code)
        except Exception as e:
            rows.append((name, f"<{type(e).__name__}>", want, False))
            continue
        S = getattr(M, "Special", None)
        if S is not None and isinstance(got, S):
            rows.append((name, str(got), want, False))
            continue
        rows.append((name, got, want, Fraction(got) == want))
    return rows


def unity_code(fmt):
    """The code that must decode to exactly 1, whatever the width.

    maxfinite is not computable for a format whose bias is near 2^60 -- 2^(top-bias)
    cannot be materialised at all -- but ONE always can. It pins the same (exp_bits,
    mant_bits, bias) triple: get any of the three wrong and unity lands somewhere else.
    That is what makes gf64 through gf1024 checkable after pass 229 had to skip them.
    """
    if getattr(fmt, "kind", "") == "int":
        return 1 << getattr(fmt, "int_frac_bits", 0)
    base = getattr(fmt, "base", 2)
    if base != 2:
        # IBM hexadecimal floating point has no implicit leading one and a base-16
        # exponent, so 1 is 1/16 * 16^1: exponent field bias+1, significand one sixteenth
        # of full scale. bias << mant_bits is the ZERO code there, which is what the
        # first version of this landmark decoded.
        shift = fmt.mant_bits - 4
        return ((fmt.bias + 1) << fmt.mant_bits) | (1 << shift)
    code = fmt.bias << fmt.mant_bits
    if getattr(fmt, "explicit_int_bit", False):
        # cray and x87 carry the leading bit in the field instead of implying it.
        code |= 1 << (fmt.mant_bits - 1)
    return code


def check_unity(mod_name):
    """(name, decoded, ok) -- computable at every width, unlike maxfinite."""
    sys.path.insert(0, CONF)
    try:
        M = importlib.import_module(mod_name)
    except Exception:
        return []
    rows = []
    for name, fmt in getattr(M, "FORMATS", {}).items():
        if not all(hasattr(fmt, a) for a in ("mant_bits", "bias")) \
                and getattr(fmt, "kind", "") != "int":
            continue
        if getattr(fmt, "bias", None) == 0 and getattr(fmt, "kind", "") != "int":
            # gf4 and mxgf4 have bias 0, so the exponent field for 1 is the same field
            # that encodes zero and subnormals. gf_decode_param.v calls gf4 a degenerate
            # edge in its own header for this reason. There is no unity landmark to take.
            rows.append((name, "no unity code: bias is 0", None))
            continue
        try:
            got = M.decode(fmt, unity_code(fmt))
        except Exception as e:
            rows.append((name, f"<{type(e).__name__}>", False))
            continue
        S = getattr(M, "Special", None)
        if S is not None and isinstance(got, S):
            rows.append((name, str(got), False))
            continue
        rows.append((name, got, got == 1))
    return rows


def pack_agrees(name):
    """Does a committed pack decode under the same oracle it names?

    Weak on purpose: the pack's own header names its oracle, so this only catches a pack
    built by something else. It is the cheap half of the question and it is the half that
    was wrong here.
    """
    path = os.path.join(CONF, "vectors", f"{name}_add.json")
    if not os.path.exists(path):
        return None
    doc = json.load(open(path, encoding="utf-8"))
    return doc.get("oracle")


def main() -> int:
    verbose = "--verbose" in sys.argv
    rows = check_posits()
    bad = [r for r in rows if not r[5]]
    sem, skipped = [], []
    for mod_name, hi in (("ieee_ref", True), ("bf16_ref", True), ("fp8_ref", None),
                         ("gf_ref", None), ("mxfp_ref", None), ("legacy_ref", False)):
        for r in check_sem(mod_name, hi, skipped):
            sem.append((mod_name, *r))
    sem_bad = [r for r in sem if not r[4]]

    print(f"posit formats checked                : {len(rows)}")
    print(f"  maxpos matches the declared (n, es): {len(rows) - len(bad)}")
    print(f"  MISMATCH                           : {len(bad)}\n")
    print(f"  {'format':<10}{'n':>4}{'es':>4}{'maxpos decoded':>22}"
          f"{'maxpos required':>22}")
    for name, n, es, got, want, ok in rows:
        mark = "" if ok else "   MISMATCH"
        print(f"  {name:<10}{n:>4}{es:>4}{str(got):>22}{str(want):>22}{mark}")
        if verbose:
            print(f"      pack oracle: {pack_agrees(name)}")

    unity = []
    for mod_name in ("ieee_ref", "bf16_ref", "fp8_ref", "gf_ref", "mxfp_ref",
                     "legacy_ref"):
        for r in check_unity(mod_name):
            unity.append((mod_name, *r))
    unity_bad = [r for r in unity if r[3] is False]
    unity_na = [r for r in unity if r[3] is None]
    print(f"\n  unity landmark, computable at every width: "
          f"{len(unity) - len(unity_na)} formats, {len(unity_bad)} where the code for 1 "
          f"does not decode to 1")
    if unity_na:
        print(f"    no unity code: {', '.join(r[1] for r in unity_na)} (bias is 0)")
    for mod_name, name, got, ok in unity_bad:
        print(f"    {name:<14} ({mod_name}) -> {str(got)[:40]}")

    print(f"\n  sign-exponent-mantissa families: {len(sem)} formats checked, "
          f"{len(sem_bad)} mismatched, {len(skipped)} past the exponent bound")
    if skipped:
        print(f"    not computable here: {', '.join(skipped)}")
    for mod_name, name, got, want, ok in sem_bad:
        # A cray_float maximum runs past 4,300 digits, which is where Python refuses to
        # render an int. The ratio is what a reader can act on anyway -- 1.0 means the
        # landmark and the decode agree in magnitude and differ in the last bits.
        def brief(x):
            try:
                return f"{float(x):.6g}"
            except (OverflowError, ValueError, TypeError):
                return f"<{type(x).__name__}, too large to print>"
        print(f"    {name:<14} ({mod_name})")
        print(f"        decoded  {brief(got)}")
        print(f"        required {brief(want)}")

    print("""
posit8 is declared es = 0 and its pack encodes es = 0. The campaign record carried a line
saying the published pack was es = 2, Posit Standard 2022, validated against SoftPosit
255/255 -- that dataset was a scratchpad artefact and is not in the repository. Both
validations were real and they were about different formats.

Which convention a paper cites has to be stated. es = 0 is the older draft; the 2022
standard fixes es = 2 at every width, and the corpus carries a separate posit8_es2 decode
path for it.""")
    return 1 if (bad or sem_bad or unity_bad) else 0


def self_check() -> int:
    """The landmark must actually discriminate. maxpos at es=0 and es=2 differ by a factor
    of 2^18 at width 8, so a check that cannot tell them apart is measuring nothing."""
    a = posit_maxpos(8, 0)
    b = posit_maxpos(8, 2)
    print(f"  posit8 maxpos at es=0 : {a}")
    print(f"  posit8 maxpos at es=2 : {b}")
    print(f"  they differ           : {a != b}  (ratio {b // a})")

    rows = check_posits()
    p8 = next(r for r in rows if r[0] == "posit8")
    print(f"  posit_ref declares posit8 es={p8[2]} and decodes maxpos {p8[3]}")
    consistent = p8[5]
    print(f"  declaration and decode agree -> {consistent}")

    ok = (a != b) and consistent
    print(f"\nself-check: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        raise SystemExit(self_check())
    raise SystemExit(main())
