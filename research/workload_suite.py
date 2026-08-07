#!/usr/bin/env python3
"""The remaining five workloads, so all seven can be run.

The paper names seven: four ML -- matrix multiply, gradient accumulation,
dynamic range, attention softmax -- and three hold-out -- convolution,
polynomial evaluation, linear solve. Pass 260 found six of them existed in no
script here. `research/workload_matmul.py` supplied matrix multiply and
`dynamic_range` was already in `research/format_benchmark.py`; this supplies the
other five.

Method, uniform across all of them: run the computation twice, once as a
reference and once with every intermediate rounded into the format through its
own oracle, then report the relative error.

The reference is exact rational arithmetic wherever the workload is closed under
it -- gradient accumulation, convolution, polynomial evaluation, linear solve.
Attention softmax needs `exp`, which is not, so there the reference is float64.
That is 2**-53 against a 16-bit format's 2**-10, three orders of magnitude of
headroom, and it is stated rather than hidden.

What this does NOT do is decide whether a format "passes". The paper's pass/fail
thresholds are not published, and inventing them would be inventing the result.
It reports the errors and leaves the threshold to whoever sets it.

Usage:  python3 research/workload_suite.py [--trials 12]
"""
import math
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


def q(mod, fmt, x):
    """Round into the format and back; None if it leaves the format."""
    v = mod.decode(fmt, mod.encode(fmt, Fraction(x).limit_denominator(10 ** 12)))
    Special = getattr(mod, "Special", None)
    if Special is not None and isinstance(v, Special):
        return None
    return v


def rel(got, exact):
    if got is None:
        return None
    if exact == 0:
        return None
    return abs(Fraction(got) - Fraction(exact)) / abs(Fraction(exact))


# ---------------------------------------------------------------- workloads

def gradient_accumulation(mod, fmt, r, n=256):
    """Sum n small updates. Exact reference; the format accumulates step by step."""
    g = [Fraction(r.gauss(0, 1e-3)).limit_denominator(10 ** 12) for _ in range(n)]
    exact = sum(g)
    acc = q(mod, fmt, 0)
    for x in g:
        acc = q(mod, fmt, acc + q(mod, fmt, x)) if acc is not None else None
    return rel(acc, exact)


def attention_softmax(mod, fmt, r, n=32):
    """softmax over n logits. Reference is float64 -- exp is not rational."""
    x = [r.uniform(-4, 4) for _ in range(n)]
    mx = max(x)
    ex = [math.exp(v - mx) for v in x]
    s = sum(ex)
    ref = [e / s for e in ex]

    xf = [q(mod, fmt, v) for v in x]
    if any(v is None for v in xf):
        return None
    mxf = max(xf)
    exf = [q(mod, fmt, math.exp(float(v - mxf))) for v in xf]
    if any(v is None for v in exf):
        return None
    sf = q(mod, fmt, 0)
    for e in exf:
        sf = q(mod, fmt, sf + e) if sf is not None else None
    if not sf:
        return None
    out = [q(mod, fmt, Fraction(e) / Fraction(sf)) for e in exf]
    worst = Fraction(0)
    for o, rf in zip(out, ref):
        if o is None or rf == 0:
            continue
        worst = max(worst, abs(Fraction(o) - Fraction(rf).limit_denominator(10 ** 12))
                    / Fraction(rf).limit_denominator(10 ** 12))
    return worst


def convolution(mod, fmt, r, n=64, k=5):
    """1-D convolution, valid region. Exact reference, NORMWISE error.

    Divided by sum|s*k| rather than by |exact|. With the componentwise form this
    workload reported about 54% for BF16, GF14 and GF16 alike -- three formats,
    one number, because a few output taps cancelled almost completely. That is
    conditioning, not precision, and dividing by the scale of the work separates
    them.
    """
    sig = [Fraction(r.uniform(-1, 1)).limit_denominator(10 ** 9) for _ in range(n)]
    ker = [Fraction(r.uniform(-1, 1)).limit_denominator(10 ** 9) for _ in range(k)]
    worst = Fraction(0)
    for i in range(n - k + 1):
        exact = sum(sig[i + t] * ker[t] for t in range(k))
        acc = q(mod, fmt, 0)
        for t in range(k):
            p = q(mod, fmt, sig[i + t] * ker[t])
            acc = q(mod, fmt, acc + p) if (acc is not None and p is not None) else None
        denom = sum(abs(sig[i + t] * ker[t]) for t in range(k))
        if acc is not None and denom != 0:
            worst = max(worst, abs(Fraction(acc) - exact) / denom)
    return worst


def polynomial(mod, fmt, r, deg=12):
    """Horner evaluation. Exact reference."""
    c = [Fraction(r.uniform(-1, 1)).limit_denominator(10 ** 9) for _ in range(deg + 1)]
    x = Fraction(r.uniform(-1.5, 1.5)).limit_denominator(10 ** 9)
    exact = Fraction(0)
    for a in c:
        exact = exact * x + a
    acc = q(mod, fmt, 0)
    xf = q(mod, fmt, x)
    for a in c:
        if acc is None or xf is None:
            return None
        acc = q(mod, fmt, q(mod, fmt, acc * xf) + q(mod, fmt, a))
    return rel(acc, exact)


def linear_solve(mod, fmt, r, n=6):
    """Gaussian elimination with partial pivoting. Exact reference solution."""
    A = [[Fraction(r.uniform(-1, 1)).limit_denominator(10 ** 9) for _ in range(n)]
         for _ in range(n)]
    for i in range(n):                     # diagonally dominant: solvable
        A[i][i] += Fraction(n)
    b = [Fraction(r.uniform(-1, 1)).limit_denominator(10 ** 9) for _ in range(n)]

    def solve(M, v, rnd):
        M = [row[:] for row in M]
        v = v[:]
        for col in range(n):
            p = max(range(col, n), key=lambda i: abs(M[i][col]))
            M[col], M[p] = M[p], M[col]
            v[col], v[p] = v[p], v[col]
            for i in range(col + 1, n):
                if M[col][col] == 0:
                    return None
                f = M[i][col] / M[col][col]
                if rnd:
                    f = q(mod, fmt, f)
                    if f is None:
                        return None
                for j in range(col, n):
                    M[i][j] = M[i][j] - f * M[col][j]
                    if rnd:
                        M[i][j] = q(mod, fmt, M[i][j])
                        if M[i][j] is None:
                            return None
                v[i] = v[i] - f * v[col]
                if rnd:
                    v[i] = q(mod, fmt, v[i])
                    if v[i] is None:
                        return None
        x = [Fraction(0)] * n
        for i in range(n - 1, -1, -1):
            s = v[i] - sum(M[i][j] * x[j] for j in range(i + 1, n))
            if M[i][i] == 0:
                return None
            x[i] = s / M[i][i]
            if rnd:
                x[i] = q(mod, fmt, x[i])
                if x[i] is None:
                    return None
        return x

    ex = solve(A, b, False)
    got = solve(A, b, True)
    if ex is None or got is None:
        return None
    worst = Fraction(0)
    for g, e in zip(got, ex):
        v = rel(g, e)
        if v is not None:
            worst = max(worst, v)
    return worst


WORKLOADS = [
    ("gradient accum", gradient_accumulation),
    ("attention softmax", attention_softmax),
    ("convolution", convolution),
    ("polynomial", polynomial),
    ("linear solve", linear_solve),
]


def main():
    trials = 12
    if "--trials" in sys.argv:
        trials = int(sys.argv[sys.argv.index("--trials") + 1])
    print("five of the seven workloads -- matrix multiply is in workload_matmul.py,")
    print("dynamic range is in format_benchmark.py. %d trials each." % trials)
    print("relative error, worst trial / median trial. n/a = every trial left the format.")
    print()
    head = "%-18s" % "workload"
    for label, _m, _f, M in FORMATS:
        head += " %-14s" % ("%s(M%s)" % (label, M))
    print(head)
    medians = {}
    for wname, fn in WORKLOADS:
        row = "%-18s" % wname
        for label, mod, fmt, M in FORMATS:
            vals = []
            for s in range(trials):
                r = random.Random(4000 + s)
                v = fn(mod, fmt, r)
                if v is not None:
                    vals.append(float(v))
            if not vals:
                row += " %-14s" % "n/a"
            else:
                med = statistics.median(vals)
                medians[(wname, label)] = med
                row += " %6.2f/%-7.2f" % (100 * max(vals), 100 * med)
        print(row)
    print()
    print("Reference is exact rational arithmetic except for attention softmax,")
    print("where exp forces float64 -- 2**-53 against a 16-bit format's 2**-10.")
    print("No pass/fail threshold is applied: the paper's are not published, and")
    print("inventing one would be inventing the result.")
    print()

    # Item 10 of the corrections package. Both abstracts say "no single format
    # dominates"; the finding is that posit16 does, over GF16, on every error
    # workload here.
    #
    # What gets asserted is the ORDERING, not the digits. The medians move with the
    # seed and the trial count; the ordering is the claim, and pinning 0.15 against
    # 0.29 would make the check fail on sampling rather than on the finding. This is
    # the same distinction pass 289 drew for item 3, where the finding is the gap
    # between 8.1x and 8.7x rather than either figure.
    print("ITEM 10 -- does posit16 still beat GF16 on every workload here?")
    beaten, lost = [], []
    for wname, _ in WORKLOADS:
        p16 = medians.get((wname, "posit16"))
        g16 = medians.get((wname, "GF16"))
        if p16 is None or g16 is None:
            continue
        (beaten if p16 <= g16 else lost).append(
            (wname, 100 * p16, 100 * g16))
    for wname, a, b in beaten:
        print("  %-18s posit16 %6.2f  <=  GF16 %6.2f" % (wname, a, b))
    for wname, a, b in lost:
        print("  %-18s posit16 %6.2f   >   GF16 %6.2f   <<< GF16 WINS HERE"
              % (wname, a, b))
    print()
    print("  posit16 lower on %d of %d, higher on %d"
          % (len(beaten), len(beaten) + len(lost), len(lost)))
    if lost:
        print("  Item 10 says posit16 dominates. It no longer does on every")
        print("  workload here -- the item needs narrowing to the ones it still wins.")
        return 1
    print("  Item 10 holds. Note this covers the workloads in THIS file; the two")
    print("  matmul rows live in research/workload_matmul.py and are not counted here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
