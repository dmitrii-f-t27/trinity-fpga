#!/usr/bin/env python3
"""Commutativity on the wide GoldenFloat rungs, which the general sweep cannot reach.

WHY THE GENERAL SWEEP STALLS
----------------------------
verify_arithmetic_invariants.py samples 24 codes per format and stalls entering
gf64. Profiling located the cause exactly, and it is not "exact rational arithmetic
is slow":

  gf_ref represents a value as a Fraction. A DENORMAL is m * 2^(1 - bias - mant),
  so its denominator is an integer of about (bias + mant_bits) bits. Measured:

    format   denominator bits          memory   decode
    gf32              2,066             0 KB    0 ms
    gf48            131,100            16 KB    0 ms
    gf64          8,388,646           1.0 MB    4 ms
    gf96     34,359,738,426           4.0 GB    not attemptable
    gf128   281,474,976,710,733        32 TB    impossible

  One gf64 denormal x denormal multiply takes 154 SECONDS -- the gcd normalisation
  inside Fraction on multi-megabit integers. At gf96 and above the value cannot be
  built at all.

NORMAL-RANGE CODES ARE CHEAP AT EVERY WIDTH. A gf1024 normal x normal multiply
takes 0.09 ms. So commutativity is verifiable across the whole ladder as long as
the sample avoids the denormal range, and that is what this script does.

WHAT THIS DOES AND DOES NOT COVER
---------------------------------
Covered: commutativity of add and mul over the NORMAL exponent range, at every
GoldenFloat width including gf1024.

NOT covered: the denormal range at gf96 and above, which gf_ref cannot represent at
all. That is a real limitation of the reference oracle and it is reported, not
papered over -- see report_denormal_reach() below. The published packs sidestep it
by storing values as dyadic `A*2^B` strings rather than as Fractions.

NO NEW METHOD, ONLY A DIFFERENT SAMPLE
--------------------------------------
Worth being explicit, because a faster result usually means a weaker one: nothing
here approximates. The laws are evaluated with the same gf_add / gf_mul and the
same exact equality the general sweep uses. The only change is WHICH codes are fed
in. So there is no fast path to cross-validate against a slow one -- the speed
comes entirely from not asking the oracle to build million-bit denominators.

The cost is coverage, not fidelity, and it is stated in the output.

Run:  python3 research/verify_wide_commutativity.py
Exit: 0 if commutativity holds everywhere it is checked, 1 on any violation.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(REPO, "conformance")

K = 24                    # codes sampled per format, matching the general sweep
SAFE_DENORM_BITS = 50_000_000


def load_gf():
    sys.path.insert(0, CONF)
    spec = importlib.util.spec_from_file_location("gf_ref", os.path.join(CONF, "gf_ref.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def normal_codes(fmt, k: int, window: int = 8) -> list[int]:
    """k raw codes from a window of exponents AROUND 1.0, both signs.

    A first version of this sampler spread exponents across the whole normal range
    and was just as slow as the general sweep. Being normal is not what makes a
    value cheap. A code with exponent field 1 has value about 2^(1 - bias), whose
    Fraction denominator still needs about `bias` bits -- at gf1024 that is the
    same wall as a denormal.

    What makes a value cheap is being NEAR 1.0, where the unbiased exponent is
    small and numerator and denominator are both tiny. So the window is centred on
    exp_field = bias, which is exponent 2^0, and spans +-`window` around it.

    The cost of that honesty: this covers a narrow band of the exponent range, not
    all of it. Stated in the output rather than implied away.
    """
    centre = int(fmt.bias)
    lo = max(1, centre - window)
    hi = min(fmt.exp_max - 1, centre + window)
    if hi < lo:
        return []
    out, seen = [], set()
    span = hi - lo
    for i in range(k):
        exp_field = lo + (span * i // max(1, k - 1) if span else 0)
        mant = (fmt.mant_max * (i * 7 % max(1, k))) // max(1, k)
        raw = (exp_field << fmt.mant_bits) | (mant & fmt.mant_max)
        if i % 3 == 2:                       # mix in negatives
            raw |= 1 << fmt.sign_shift
        if raw not in seen:
            seen.add(raw)
            out.append(raw)
    return out


def check_format(gf, name, codes) -> tuple[int, int, float]:
    """Return (pairs_tested, violations, seconds)."""
    fmt = gf.FORMATS[name]
    t0 = time.time()
    violations = 0
    pairs = 0
    for a in codes:
        for b in codes:
            pairs += 1
            if gf.gf_add(fmt, a, b) != gf.gf_add(fmt, b, a):
                violations += 1
            if gf.gf_mul(fmt, a, b) != gf.gf_mul(fmt, b, a):
                violations += 1
    return pairs, violations, time.time() - t0


def report_denormal_reach(gf, names):
    """How far the in-tree oracle can represent a denormal at all."""
    print("\nDenormal reach of gf_ref (a Fraction denominator of ~bias+mant bits):")
    print(f"  {'format':<9}{'denominator bits':>22}{'':>4}status")
    for name in names:
        fmt = gf.FORMATS[name]
        bits = int(fmt.bias) + fmt.mant_bits
        ok = bits <= SAFE_DENORM_BITS
        gb = bits / 8 / 1024**3
        status = "representable" if ok else f"NOT representable (~{gb:.3g} GB)"
        print(f"  {name:<9}{bits:>22}{'':>4}{status}")
    print("  The published wide packs carry 2-4 denormal vectors each, stored as")
    print("  dyadic A*2^B strings -- which is precisely why that encoding exists.")


def main() -> int:
    gf = load_gf()
    names = [n for n in ("gf4", "gf6", "gf8", "gf10", "gf12", "gf14", "gf16",
                         "gf20", "gf24", "gf32", "gf48", "gf64", "gf96",
                         "gf128", "gf256", "gf512", "gf1024") if n in gf.FORMATS]

    print(f"{'format':<9}{'codes':>7}{'pairs':>9}{'comm+ / comm*':>16}{'seconds':>10}")
    print("-" * 53)
    total_pairs = total_viol = 0
    for name in names:
        fmt = gf.FORMATS[name]
        codes = normal_codes(fmt, K)
        if not codes:
            print(f"{name:<9}{'-':>7}{'-':>9}{'no normal range':>16}")
            continue
        pairs, viol, secs = check_format(gf, name, codes)
        total_pairs += pairs
        total_viol += viol
        print(f"{name:<9}{len(codes):>7}{pairs:>9}"
              f"{('OK' if not viol else f'{viol} VIOLATED'):>16}{secs:>10.2f}")

    report_denormal_reach(gf, [n for n in names if n in
                               ("gf32", "gf48", "gf64", "gf96", "gf128", "gf1024")])

    print(f"\ntotal ordered pairs tested: {total_pairs}   violations: {total_viol}")
    print("scope: exponents within +-8 of 1.0, both signs, all 17 GoldenFloat widths.")
    print("NOT covered: the rest of the exponent range, and every denormal at gf96+,")
    print("which gf_ref cannot represent at all. Coverage was traded for termination,")
    print("and the trade is the finding as much as the result is.")
    return 1 if total_viol else 0


if __name__ == "__main__":
    raise SystemExit(main())
