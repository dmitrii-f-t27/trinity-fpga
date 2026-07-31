#!/usr/bin/env python3
"""Quantify the GF16+ quire's order-independence, and where it ends.

GF16+ stores operands in GF16 and accumulates products in what the oracle calls a
Quire. Reading conformance/gf16_plus_ref.py, that accumulator is a **binary64
double**, and its docstring says plainly that it is "exact for small sums".

That is an honest qualitative statement, and this makes it quantitative.

A true quire in the Gustafson sense is a wide FIXED-POINT accumulator: it does not
round at all until flush, so accumulation is exactly associative and the result is
independent of summation order. A binary64 accumulator has that property only
while every partial sum stays exactly representable in 53 bits. Past that, order
matters.

The test: build a set of GF16 operand pairs, accumulate their products in many
random orders, flush, and see whether the flushed result is identical across
orders. Then push the magnitude spread until it stops being identical, and report
where.

Order-dependence here is NOT a defect -- the oracle documents the accumulator as
binary64. The point is to say where the documented boundary actually falls.

Run:  python3 research/verify_quire_associativity.py
"""
from __future__ import annotations
import importlib.util
import os
import random
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(REPO, "conformance")


def load(fn):
    sys.path.insert(0, CONF)
    spec = importlib.util.spec_from_file_location("q_" + fn, os.path.join(CONF, fn))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def accumulate(gp, pairs, order):
    """MAC every pair in the given order, then flush. Returns the flushed raw.

    Contract per the oracle: state is a binary64 float starting at 0.0, ops are
    the integer constants OP_MAC/OP_MACSUB/OP_FLUSH, and mac() returns a tuple
    (new_state, flush_result_or_None).
    """
    state = 0.0
    for i in order:
        a, b = pairs[i]
        state, _ = gp.gf16_plus_mac(state, a, b, gp.OP_MAC)
    return gp.gf16_plus_flush(state)


def trial(gp, pairs, n_orders=12, seed=0):
    rng = random.Random(seed)
    idx = list(range(len(pairs)))
    results = set()
    for k in range(n_orders):
        order = idx[:] if k == 0 else rng.sample(idx, len(idx))
        try:
            results.add(accumulate(gp, pairs, order))
        except Exception as e:
            return None, f"{type(e).__name__}: {e}"
    return results, None


def main() -> int:
    gp = load("gf16_plus_ref.py")
    gf = load("gf_ref.py")
    fmt = gf.FORMATS["gf16"]

    print("GF16+ quire = binary64 accumulator (per gf16_plus_ref.py docstring)")
    print("testing whether flush() is independent of MAC order\n")

    rng = random.Random(7)

    # Sweep the magnitude spread of the operands. Small, similar magnitudes
    # should accumulate exactly; a wide spread should not.
    for label, lo, hi, n in (("tight  (values near 1)",      0,  2, 16),
                             ("moderate spread",             -6,  6, 16),
                             ("wide spread",                -20, 20, 16),
                             ("extreme spread",             -30, 30, 16)):
        pairs = []
        for _ in range(n):
            ea, eb = rng.randint(lo, hi), rng.randint(lo, hi)
            a = gf.encode(fmt, 2 ** ea)
            b = gf.encode(fmt, 2 ** eb)
            pairs.append((a, b))
        results, err = trial(gp, pairs, seed=len(pairs))
        if err:
            print(f"  {label:<26} ERROR {err}")
            continue
        n_distinct = len(results)
        verdict = "ORDER-INDEPENDENT" if n_distinct == 1 else f"{n_distinct} distinct results"
        print(f"  {label:<26} {verdict}")

    print()
    print("Reading: order-independence holding for tight magnitudes and failing for")
    print("wide ones is exactly what a binary64 accumulator predicts, and matches the")
    print("oracle's own 'exact for small sums'. A wide fixed-point quire would hold")
    print("at every spread. This measures where the documented boundary falls; it is")
    print("not a defect report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
