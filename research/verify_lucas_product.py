#!/usr/bin/env python3
"""Check the Fibonacci-product identity that CLOSURE_MEASURED cites.

    F_m * F_n = (L_{m+n} - (-1)^n * L_{m-n}) / 5

The document said this was "verified over 300 index pairs". No script for that
was in the repository. research/verify_lucas_exact.py is a different check --
it tests phi^(2n) + phi^(-2n) == L_(2n) over a single index -- so citing it as
backing would be citing the wrong file.

Exact integer arithmetic throughout: no float, no Decimal, no tolerance. F and L
come from their own recurrences rather than from Binet, so nothing here depends
on a floating-point phi. Negative indices use L_{-k} = (-1)^k * L_k, which is
where a naive implementation goes wrong and why m < n is swept as well as m > n.

    python3 verify_lucas_product.py            # default sweep, then the controls
    python3 verify_lucas_product.py --max 200  # wider

Exit 0 only if every pair holds AND both perturbed forms are seen to fail.
"""
import argparse
import sys


def fib_lucas(n_max: int):
    """F[0..n], L[0..n] by recurrence. F0=0,F1=1; L0=2,L1=1."""
    F = [0, 1]
    L = [2, 1]
    for i in range(2, n_max + 1):
        F.append(F[-1] + F[-2])
        L.append(L[-1] + L[-2])
    return F, L


def lucas_signed(L, k: int) -> int:
    """L_k for any integer k, via L_{-k} = (-1)^k * L_k."""
    return L[k] if k >= 0 else (L[-k] if (-k) % 2 == 0 else -L[-k])


def rhs(L, m: int, n: int, *, sign: bool = True, negative_index: bool = True) -> int:
    """The right-hand side. The two flags exist to build wrong versions on purpose."""
    s = (-1) ** n if sign else 1
    lo = lucas_signed(L, m - n) if negative_index else L[abs(m - n)]
    return (L[m + n] - s * lo) // 5


def sweep(max_index: int, **kw):
    F, L = fib_lucas(2 * max_index + 2)
    checked = 0
    bad = []
    for m in range(max_index + 1):
        for n in range(max_index + 1):
            left = F[m] * F[n]
            right_num = L[m + n] - ((-1) ** n if kw.get("sign", True) else 1) * (
                lucas_signed(L, m - n) if kw.get("negative_index", True) else L[abs(m - n)]
            )
            checked += 1
            # Exact: the numerator must be divisible by 5 as well as equal.
            if right_num % 5 != 0 or left != right_num // 5:
                if len(bad) < 5:
                    bad.append((m, n, left, right_num))
    return checked, bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=120,
                    help="sweep m,n in 0..max (default 120 -> 14,641 pairs)")
    args = ap.parse_args()

    checked, bad = sweep(args.max)
    print(f"  identity : F_m*F_n == (L_(m+n) - (-1)^n * L_(m-n)) / 5")
    print(f"  range    : m, n in 0..{args.max}, both orders, exact integers")
    print(f"  pairs    : {checked - len(bad)}/{checked}")
    if bad:
        for m, n, left, num in bad:
            print(f"    FAIL m={m} n={n}: F_m*F_n={left}, numerator={num}")

    # A checker that cannot fail is not a checker. Two deliberate corruptions,
    # each removing one thing the identity actually needs.
    print("  negative controls (each must FAIL):")
    controls = [
        ("drop the (-1)^n factor", dict(sign=False)),
        ("use L_|m-n| instead of L_(m-n)", dict(negative_index=False)),
    ]
    controls_ok = True
    for label, kw in controls:
        c, b = sweep(min(args.max, 40), **kw)
        if b:
            m, n, left, num = b[0]
            print(f"    {label}: {c - len(b)}/{c} -- first break m={m} n={n}")
        else:
            print(f"    {label}: {c}/{c} -- DID NOT BREAK, the control is useless")
            controls_ok = False

    ok = not bad and controls_ok
    print("  VERDICT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
