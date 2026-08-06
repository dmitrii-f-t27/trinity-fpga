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

# (label, module, format, mantissa bits)
FORMATS = [
    ("BF16", bf16_ref, bf16_ref.FORMATS["bfloat16"], 7),
    ("GF14", gf_ref, gf_ref.FORMATS["gf14"], 8),
    ("GF16", gf_ref, gf_ref.FORMATS["gf16"], 9),
    ("FP16", ieee_ref, ieee_ref.FORMATS["binary16"], 10),
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


def matmul_error(mod, fmt, A, B, n, k):
    """Max relative error of an in-format matmul against the exact product."""
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
            if exact == 0:
                continue
            rel = abs(Fraction(acc) - exact) / abs(exact)
            worst = max(worst, rel)
    return float(worst), overflowed


def main():
    n = 8
    trials = 20
    if "--n" in sys.argv:
        n = int(sys.argv[sys.argv.index("--n") + 1])
    if "--trials" in sys.argv:
        trials = int(sys.argv[sys.argv.index("--trials") + 1])
    k = n

    print("matrix multiply, %dx%d, %d trials per distribution" % (n, n, trials))
    print("max relative error over output entries, worst trial / median trial")
    print()
    header = "%-14s" % "distribution"
    for label, _m, _f, M in FORMATS:
        header += " %-18s" % ("%s (M=%d)" % (label, M))
    print(header)

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
                e, ov = matmul_error(mod, fmt, A, B, n, k)
                worst.append(e)
                overflows += ov
            row += " %7.2f%% /%6.2f%%%s" % (
                100 * max(worst), 100 * statistics.median(worst),
                ("*%d" % overflows) if overflows else "  ")
        print(row)

    print()
    print("* = output entries that overflowed the format and were skipped.")
    print()
    print("The claim under test: BF16 (M=7) shows 1.5-10% max error depending on")
    print("input distribution, GF14 (M=8) is borderline, GF16 (M=9) is robust.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
