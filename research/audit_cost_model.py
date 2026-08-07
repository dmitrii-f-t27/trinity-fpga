#!/usr/bin/env python3
"""Does LUT_ADD = 1.63 W^2 with R^2 >= 0.97 fit any subset of the published table?

arXiv 2606.05017 states a quadratic area law with a single coefficient, an R^2
floor, and eleven measured points. Item 5 of research/CORRECTIONS_PACKAGE_both_
preprints.md says no subset of the paper's own table produces that combination.

That correction was computed in a session and written into a markdown table, with
no script behind it. A correction with no tool to regenerate it is the same defect
it complains about, so this is the tool. It reads the measured rows of
research/COMPLETE_LUT_TABLE.md -- the bolded ones, which are the yosys
measurements; the tilde rows are extrapolations from the very law under test and
including them would be circular -- and refits.

WHAT IS FITTED
--------------
    through the origin      LUT = c * W^2, c = sum(W^2 * LUT) / sum(W^4),
                            the least-squares solution for a one-parameter model
    free exponent           LUT = a * W^b, by least squares on log LUT vs log W

R^2 is reported against the mean of the data in both cases, which is the
convention that makes 0.97 a meaningful floor. For the through-origin fit that
number can be negative for a bad model; that is informative, not a bug.

Usage:  python3 research/audit_cost_model.py [--verbose]

Exits non-zero if the paper's stated combination DOES fit -- i.e. if the
correction has stopped being true and needs withdrawing.
"""
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TABLE = os.path.join(HERE, "COMPLETE_LUT_TABLE.md")

CLAIM_C = 1.63
CLAIM_R2 = 0.97
CLAIM_N = 11
TOL_C = 0.05          # how close counts as reproducing 1.63

ROW = re.compile(
    r"^\|\s*GF(\d+)\s*\|\s*(\d+)\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|")


def cell(text):
    """(value, measured). Bold means yosys measured it; a tilde means the value was
    extrapolated FROM the scaling law, so feeding it back in would be circular."""
    t = text.strip()
    measured = t.startswith("**")
    t = t.strip("*").replace(",", "").strip()
    if t.startswith("~"):
        return (float(t[1:]) if t[1:] else None), False
    try:
        return float(t), measured
    except ValueError:
        return None, False


def read_table():
    add, mul = [], []
    for line in open(TABLE, encoding="utf-8"):
        m = ROW.match(line)
        if not m:
            continue
        w = int(m.group(2))
        a, a_meas = cell(m.group(3))
        u, u_meas = cell(m.group(4))
        if a is not None and a_meas:
            add.append((w, a))
        if u is not None and u_meas:
            mul.append((w, u))
    return sorted(add), sorted(mul)


def fit_quadratic(pts):
    """LUT = c * W^2 through the origin, plus R^2 against the mean."""
    num = sum(w * w * y for w, y in pts)
    den = sum(w ** 4 for w in (p[0] for p in pts))
    c = num / den
    ybar = sum(y for _, y in pts) / len(pts)
    ss_res = sum((y - c * w * w) ** 2 for w, y in pts)
    ss_tot = sum((y - ybar) ** 2 for _, y in pts)
    return c, (1 - ss_res / ss_tot if ss_tot else float("nan"))


def fit_power(pts):
    """LUT = a * W^b by least squares on the logs.

    Returns (a, b, R2_linear, R2_log). BOTH, because the corrections package
    reported the log-space number in a table sitting directly beneath quadratic
    fits whose R2 was linear-space, with nothing saying they were different
    statistics. For ADD over all 14 points that is 0.9746 against 0.9913, and for
    MUL it is 0.9044 against 0.6254 -- a gap wide enough to change what a reader
    concludes, in an argument whose whole subject is an R2 threshold.

    Neither is wrong. Fitting on logs weights the small formats far more heavily,
    which is often what you want for a scaling law; measuring fit against the raw
    counts is what "R2 >= 0.97" means when a paper says it about LUTs. Reporting
    one under the other's heading is what was wrong.
    """
    n = len(pts)
    X = [math.log(w) for w, _ in pts]
    Y = [math.log(y) for _, y in pts]
    sx, sy = sum(X), sum(Y)
    sxx = sum(x * x for x in X)
    sxy = sum(x * y for x, y in zip(X, Y))
    b = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    log_a = (sy - b * sx) / n
    a = math.exp(log_a)

    ybar = sum(y for _, y in pts) / n
    ss_res = sum((y - a * w ** b) ** 2 for w, y in pts)
    ss_tot = sum((y - ybar) ** 2 for _, y in pts)
    r2_lin = 1 - ss_res / ss_tot if ss_tot else float("nan")

    lbar = sy / n
    lr = sum((y - (log_a + b * x)) ** 2 for x, y in zip(X, Y))
    lt = sum((y - lbar) ** 2 for y in Y)
    r2_log = 1 - lr / lt if lt else float("nan")
    return a, b, r2_lin, r2_log


def main():
    verbose = "--verbose" in sys.argv
    add, mul = read_table()
    if len(add) < 6:
        print("could not read the measured ADD rows from %s" % TABLE)
        return 2

    print("measured points read from COMPLETE_LUT_TABLE.md (bold only):")
    print("   ADD : %d  W = %s" % (len(add), ", ".join(str(w) for w, _ in add)))
    print("   MUL : %d  W = %s" % (len(mul), ", ".join(str(w) for w, _ in mul)))
    print()

    print("LUT = c * W^2 fitted through the origin")
    print("%-28s %4s %8s %9s" % ("subset", "n", "c", "R^2"))
    reproduces = []
    for label, pts in (
            ("ADD, GF4-GF24", [p for p in add if p[0] <= 24]),
            ("ADD, GF4-GF32", [p for p in add if p[0] <= 32]),
            ("ADD, GF4-GF48", [p for p in add if p[0] <= 48]),
            ("ADD, GF4-GF64", [p for p in add if p[0] <= 64]),
            ("ADD, all measured", add),
            ("MUL, GF4-GF24", [p for p in mul if p[0] <= 24]),
            ("MUL, all measured", mul)):
        if len(pts) < 3:
            continue
        c, r2 = fit_quadratic(pts)
        hit = (abs(c - CLAIM_C) <= TOL_C and r2 >= CLAIM_R2)
        if hit:
            reproduces.append((label, len(pts), c, r2))
        print("%-28s %4d %8.3f %9.4f%s"
              % (label, len(pts), c, r2, "   <- matches the claim" if hit else ""))

    print()
    print("per-point c = LUT / W^2, which the claim treats as a constant:")
    print("   %s" % "  ".join("W%d" % w for w, _ in add))
    print("   %s" % "  ".join("%.2f" % (y / (w * w)) for w, y in add))
    print()

    print("LUT = a * W^b, exponent free")
    print("%-28s %4s %8s %8s %10s %9s"
          % ("subset", "n", "a", "b", "R^2 linear", "R^2 log"))
    seen = set()
    for label, pts in (("ADD, all measured", add),
                       ("MUL, GF4-GF32", [p for p in mul if p[0] <= 32]),
                       ("MUL, all measured", mul)):
        if len(pts) < 3:
            continue
        sig = tuple(pts)
        if sig in seen:      # every measured MUL point is W<=32; do not print twice
            continue
        seen.add(sig)
        a, b, r2l, r2g = fit_power(pts)
        print("%-28s %4d %8.3f %8.3f %10.4f %9.4f"
              % (label, len(pts), a, b, r2l, r2g))
    print("   R^2 linear is measured against the LUT counts; R^2 log against their")
    print("   logarithms. The corrections package printed the log column under a")
    print("   heading whose other tables were linear. Both are reported here.")

    print()
    n11 = [p for p in add if p[0] <= 48]
    if len(n11) == CLAIM_N:
        c11, r11 = fit_quadratic(n11)
        print("the only ADD subset with exactly %d points (GF4-GF48) gives "
              "c = %.3f, R^2 = %.4f" % (CLAIM_N, c11, r11))

    print()
    if reproduces:
        print("A SUBSET NOW REPRODUCES c=%.2f with R^2>=%.2f:" % (CLAIM_C, CLAIM_R2))
        for label, n, c, r2 in reproduces:
            print("    %s  n=%d c=%.3f R^2=%.4f" % (label, n, c, r2))
        print("Item 5 of the corrections package should be withdrawn.")
        return 1
    print("No subset reproduces c = %.2f with R^2 >= %.2f." % (CLAIM_C, CLAIM_R2))
    print("Item 5 stands. This checks the FIT, not the measurements -- whether the")
    print("published LUT counts are right is research/audit_lut_table.py's question.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
