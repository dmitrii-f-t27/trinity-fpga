#!/usr/bin/env python3
"""The matrix-multiply workload, implemented -- because it was not in the repo.

The paper's headline is "seven formats across seven workloads -- four ML (matrix
multiply, gradient accumulation, dynamic range, attention softmax) and three
hold-out (convolution, polynomial evaluation, linear solve)", and its central
result is that GF16 is the minimum-width IEEE-style format passing all seven.

Three of the supporting numbers reproduce from this repository: the dynamic-range
ladder (pass 251), the training noise floor (pass 251), and the four-suite
accuracy benchmark that `research/format_benchmark.py` implements -- arithmetic,
dynamic_range, cancellation, edge_cases.

The seven-workload harness is not here. Matrix multiply, gradient accumulation,
attention softmax, convolution, polynomial evaluation and linear solve appear in
no script in the repository. So the constraint that fixes the second coordinate
of the paper's feasible corner --

    "Matrix-multiply precision requires M >= 9: BF16 (M=7) exhibits 1.5-10%
     stochastic matmul error, GF14 (M=8) is borderline, and GF16 (M=9) is robust"

-- could not be checked. This implements it.

Method: random A (n x k) and B (k x n), the product computed twice -- once
exactly over Fractions, once with every multiply and every accumulation rounded
to the format through its own oracle. The metric is the maximum relative error
over the output entries, and the sweep runs several input distributions because
the claim is explicitly distribution-dependent.

Usage:  python3 research/workload_matmul.py [--n 8] [--trials 20]
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
import mxfp_ref      # noqa: E402
import posit_ref     # noqa: E402
import takum_ref     # noqa: E402

# The seven formats the paper compares, in its own order. The last column is
# mantissa bits where the format has a fixed one; posit and takum are tapered, so
# theirs varies with the exponent and is marked "~".
FORMATS = [
    ("GF16", gf_ref, gf_ref.FORMATS["gf16"], "9"),
    ("GF12", gf_ref, gf_ref.FORMATS["gf12"], "7"),
    ("posit16", posit_ref, posit_ref.FORMATS["posit16"], "~"),
    ("MXFP8", mxfp_ref, mxfp_ref.FORMATS["mxfp8_e4m3"], "3"),
    ("BF16", bf16_ref, bf16_ref.FORMATS["bfloat16"], "7"),
    ("FP16", ieee_ref, ieee_ref.FORMATS["binary16"], "10"),
    ("takum16", takum_ref, takum_ref.FORMATS["takum16"], "~"),
]

DISTRIBUTIONS = {
    "uniform[-1,1]": lambda r: r.uniform(-1, 1),
    "uniform[0,1]": lambda r: r.uniform(0, 1),
    "normal(0,1)": lambda r: r.gauss(0, 1),
    "lognormal": lambda r: r.lognormvariate(0, 1),
    "mixed scale": lambda r: r.uniform(-1, 1) * (10 ** r.randint(-3, 3)),
}


def q(mod, fmt, x):
    """Round an exact value into the format and back, or None if it leaves the format.

    The mixed-scale distribution reaches values a 16-bit format cannot hold, and
    the oracle answers with a Special (Inf/NaN) rather than a Fraction. Treating
    that as a number is how a relative error of 184% turns into a crash; treating
    it as an overflow is what it is.
    """
    v = mod.decode(fmt, mod.encode(fmt, x))
    Special = getattr(mod, "Special", None)
    if Special is not None and isinstance(v, Special):
        return None
    return v


def matmul_error(mod, fmt, A, B, n, k, normwise=False):
    """Max error of an in-format matmul against the exact product.

    Two denominators, and the choice is the whole point.

      componentwise  |computed - exact| / |exact|
      normwise       |computed - exact| / sum |a_t * b_t|

    The componentwise form is what pass 260 measured, and it explodes wherever
    the exact result is near zero: BF16 scored 184% on uniform[-1,1] because a
    few output entries cancelled almost completely, which says nothing about the
    format's precision. The normwise form divides by the SCALE OF THE WORK
    instead of the size of the answer, which is the standard way numerical
    analysis separates conditioning from precision.
    """
    worst = Fraction(0)
    overflowed = 0
    for i in range(n):
        for j in range(n):
            exact = sum(A[i][t] * B[t][j] for t in range(k))
            acc = q(mod, fmt, Fraction(0))
            bad = False
            for t in range(k):
                prod = q(mod, fmt, A[i][t] * B[t][j])
                if prod is None or acc is None:
                    bad = True
                    break
                acc = q(mod, fmt, acc + prod)
            if bad or acc is None:
                overflowed += 1
                continue
            denom = (sum(abs(A[i][t] * B[t][j]) for t in range(k))
                     if normwise else abs(exact))
            if denom == 0:
                continue
            rel = abs(Fraction(acc) - exact) / denom
            worst = max(worst, rel)
    return float(worst), overflowed


NORMWISE = False


def main():
    global NORMWISE
    NORMWISE = "--normwise" in sys.argv
    n = 8
    trials = 20
    if "--n" in sys.argv:
        n = int(sys.argv[sys.argv.index("--n") + 1])
    if "--trials" in sys.argv:
        trials = int(sys.argv[sys.argv.index("--trials") + 1])
    k = n

    print("matrix multiply, %dx%d, %d trials per distribution" % (n, n, trials))
    print("error metric: %s" % ("NORMWISE, divided by sum|a*b|"
                                if NORMWISE else "componentwise, divided by |exact|"))
    print("max over output entries, worst trial / median trial")
    print()
    header = "%-14s" % "distribution"
    for label, _m, _f, M in FORMATS:
        header += " %-14s" % ("%s(M%s)" % (label, M))
    print(header)

    medians = {}
    for dname, draw in DISTRIBUTIONS.items():
        row = "%-14s" % dname
        for label, mod, fmt, M in FORMATS:
            worst = []
            overflows = 0
            for s in range(trials):
                r = random.Random(1000 + s)
                A = [[Fraction(draw(r)).limit_denominator(10 ** 9) for _ in range(k)]
                     for _ in range(n)]
                B = [[Fraction(draw(r)).limit_denominator(10 ** 9) for _ in range(n)]
                     for _ in range(k)]
                e, ov = matmul_error(mod, fmt, A, B, n, k, normwise=NORMWISE)
                worst.append(e)
                overflows += ov
            med = statistics.median(worst)
            medians[(dname, label)] = med
            row += " %6.2f/%-6.2f%s" % (
                100 * max(worst), 100 * med,
                ("*%d" % overflows) if overflows else "  ")
        print(row)

    print()
    print("* = output entries that overflowed the format and were skipped.")
    print()
    print("The claim under test: BF16 (M=7) shows 1.5-10% max error depending on")
    print("input distribution, GF14 (M=8) is borderline, GF16 (M=9) is robust.")
    print()

    # Item 10's other half. research/workload_suite.py checks the five non-matmul
    # workloads; these matmul rows were the two the corrections table quotes and
    # the only part of the item with nothing asserting it. Pass 289 said so
    # explicitly rather than letting 5 of 7 read as the whole claim.
    #
    # The ORDERING is asserted, not the medians, for the same reason as there: the
    # medians move with the trial count and the ordering is what item 10 says.
    print("ITEM 10 -- does posit16 still beat GF16 on every distribution here?")
    beaten, lost = [], []
    for dname in DISTRIBUTIONS:
        p16 = medians.get((dname, "posit16"))
        g16 = medians.get((dname, "GF16"))
        if p16 is None or g16 is None:
            continue
        (beaten if p16 <= g16 else lost).append((dname, 100 * p16, 100 * g16))
    for dname, a, b in beaten:
        print("  %-14s posit16 %7.2f  <=  GF16 %7.2f" % (dname, a, b))
    for dname, a, b in lost:
        print("  %-14s posit16 %7.2f   >   GF16 %7.2f   <<< GF16 WINS HERE"
              % (dname, a, b))
    print()
    print("  posit16 lower or equal on %d of %d, higher on %d"
          % (len(beaten), len(beaten) + len(lost), len(lost)))
    if lost:
        print("  Item 10 says posit16 dominates. It no longer does on every")
        print("  distribution -- the item needs narrowing to the ones it still wins.")
        return 1
    print("  Item 10 holds on the matmul half. With workload_suite's five, the")
    print("  claim is now checked across all seven of the paper's named workloads.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
