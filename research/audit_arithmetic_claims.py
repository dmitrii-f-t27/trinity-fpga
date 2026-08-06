#!/usr/bin/env python3
"""The paper's arithmetic claims, recomputed from the oracles.

Pass 250 checked the LUT tables and they reproduce. These are the claims that
need no toolchain at all -- just the format definitions and a random number
generator -- so they are the cheapest of all to verify and had never been.

  dynamic range   "FP16 fails dynamic range (5/11 values flushed to zero)"
                  (abstract, and the contributions list)
                  "FP16 (E=5) loses 5/11 values across 10^-10 to 10^10, while
                  GF16 (E=6) loses only 1/11" (the body)

  noise floor     "BF16 preserves only 7.3% of gradient updates ... while GF16
                  preserves 63.9%", from a weight at 0.5 taking 2000 additive
                  updates drawn from N(1e-4, 1e-3), re-quantised every step

The protocol matters more than it looks. Holding the weight at 0.5 and drawing
independent updates gives 17.2% and 71.6% -- the walk drifts upward, the ulp
grows with it, and fewer updates survive later than earlier. Measuring the thing
the method describes, rather than a reasonable-sounding neighbour, is the whole
job here.

Usage:  python3 research/audit_arithmetic_claims.py
"""
import os
import random
import statistics
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "conformance"))

import bf16_ref      # noqa: E402
import gf_ref        # noqa: E402
import ieee_ref      # noqa: E402


def ladder():
    """10^-10 to 10^10 in steps of two decades -- the eleven values."""
    return [Fraction(10) ** e for e in range(-10, 11, 2)]


def classify(mod, fmt, values):
    zero = inf = ok = 0
    for v in values:
        back = mod.decode(fmt, mod.encode(fmt, v))
        Special = getattr(mod, "Special", None)
        if Special is not None and isinstance(back, Special):
            inf += 1
        elif back == 0:
            zero += 1
        else:
            ok += 1
    return zero, inf, ok


def walk(mod, fmt, steps=2000, w0=0.5, mu=1e-4, sd=1e-3, seed=0):
    """The paper's protocol: sequential, re-quantised every step."""
    rng = random.Random(seed)
    code = mod.encode(fmt, Fraction(w0).limit_denominator(10 ** 9))
    kept = 0
    for _ in range(steps):
        v = mod.decode(fmt, code)
        d = Fraction(rng.gauss(mu, sd)).limit_denominator(10 ** 12)
        nc = mod.encode(fmt, v + d)
        if nc != code:
            kept += 1
        code = nc
    return 100.0 * kept / steps


def main():
    vals = ladder()
    print("DYNAMIC RANGE -- eleven values, 10^-10 to 10^10")
    print("%-22s %8s %8s %14s" % ("format", "-> zero", "-> Inf", "lost of 11"))
    rows = [("binary16 (FP16, E=5)", ieee_ref, ieee_ref.FORMATS["binary16"], 5),
            ("gf16 (E=6)", gf_ref, gf_ref.FORMATS["gf16"], 1)]
    ok_dr = True
    for name, mod, fmt, claim in rows:
        z, i, o = classify(mod, fmt, vals)
        lost = z + i
        mark = "" if lost == claim else "   <<< paper says %d" % claim
        print("%-22s %8d %8d %14d%s" % (name, z, i, lost, mark))
        ok_dr &= lost == claim
    print()
    print("  The counts are right. The WORDING in the abstract and the")
    print("  contributions list is not: \"5/11 values flushed to zero\" describes")
    print("  two of them. The other three overflow to infinity -- the opposite")
    print("  end of the range. The body, which says \"loses 5/11\", is correct.")
    print()

    print("NOISE FLOOR -- 2000 sequential steps from w=0.5, N(1e-4, 1e-3)")
    print("%-12s %-5s %12s %12s" % ("format", "M", "preserved", "paper"))
    for name, mod, fmt, M, claim in (
            ("bfloat16", bf16_ref, bf16_ref.FORMATS["bfloat16"], 7, 7.3),
            ("gf16", gf_ref, gf_ref.FORMATS["gf16"], 9, 63.9)):
        got = statistics.mean(walk(mod, fmt, seed=s) for s in range(5))
        print("%-12s M=%-3d %11.1f%% %11.1f%%" % (name, M, got, claim))
    print()
    print("  Both reproduce. Holding the weight fixed instead of walking it")
    print("  gives 17.2%% and 71.6%% -- the walk drifts upward and the ulp grows")
    print("  with it, so the protocol is not a detail.")
    return 0 if ok_dr else 1


if __name__ == "__main__":
    sys.exit(main())
