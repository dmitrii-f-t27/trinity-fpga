#!/usr/bin/env python3
"""Independent check of the Lucas-exactness claim of arXiv:2606.05017.

The abstract reports "an integer-backed Lucas-exact accumulator path verified at
500-digit precision for n = 1, ..., 256".

The underlying identity is

    phi^(2n) + phi^(-2n) = L_(2n)        (an INTEGER, the Lucas number)

with phi = (1 + sqrt 5)/2. The project's anchor phi^2 + 1/phi^2 = 3 is the n = 1
case, since L_2 = 3.

This script verifies the identity independently of any project code:
  * L_k comes from the pure integer recurrence L_0 = 2, L_1 = 1,
    L_k = L_(k-1) + L_(k-2)  -- no floating point anywhere;
  * phi^(2n) + phi^(-2n) is evaluated in Decimal at the stated 500 digits;
  * the two are compared, and the worst deviation over the whole sweep reported.

It also reports the precision headroom, because "500 digits" is only meaningful
if the largest term still fits: L_512 has ~107 integer digits, so ~390 fractional
digits remain at n = 256.

Run:  python3 research/verify_lucas_exact.py
Exit: 0 if the identity holds for every n in 1..256, 1 otherwise.
"""
from __future__ import annotations
from decimal import Decimal, getcontext
import sys

DIGITS = 500
N_MAX = 256
getcontext().prec = DIGITS


def lucas_upto(k_max: int) -> list[int]:
    """Exact integer Lucas numbers L_0..L_k_max."""
    lucas = [2, 1]
    while len(lucas) <= k_max:
        lucas.append(lucas[-1] + lucas[-2])
    return lucas


def main() -> int:
    phi = (Decimal(1) + Decimal(5).sqrt()) / Decimal(2)
    lucas = lucas_upto(2 * N_MAX)

    worst_dev = Decimal(0)
    worst_n = None
    mismatches = []

    for n in range(1, N_MAX + 1):
        two_n = 2 * n
        val = phi ** two_n + phi ** (-two_n)
        target = Decimal(lucas[two_n])
        dev = abs(val - target)
        if dev > worst_dev:
            worst_dev, worst_n = dev, n
        # Exactness is judged relative to the magnitude: at 500 digits the
        # representable resolution near L_512 (~1e107) is ~1e-392, so a residue
        # far below that is arithmetic noise, not a failed identity.
        tolerance = target.scaleb(-(DIGITS - 60))
        if dev > tolerance:
            mismatches.append((n, dev))

    l512 = lucas[2 * N_MAX]
    int_digits = len(str(l512))

    print(f"identity : phi^(2n) + phi^(-2n) == L_(2n)")
    print(f"range    : n = 1 .. {N_MAX}   (so L_2 .. L_{2*N_MAX})")
    print(f"precision: {DIGITS} decimal digits")
    print()
    print(f"L_2   = {lucas[2]}            (this is the project anchor: phi^2 + 1/phi^2 = 3)")
    print(f"L_{2*N_MAX} has {int_digits} integer digits "
          f"-> ~{DIGITS - int_digits} fractional digits of headroom at n = {N_MAX}")
    print()
    print(f"checked      : {N_MAX}")
    print(f"mismatches   : {len(mismatches)}")
    print(f"worst residue: {worst_dev:.3E} at n = {worst_n}")

    if mismatches:
        for n, dev in mismatches[:10]:
            print(f"  MISMATCH n={n}: residue {dev:.3E}")
        return 1

    print()
    print("RESULT: identity holds for every n in 1..256 at 500-digit precision.")
    print("NOTE  : this verifies the MATHEMATICAL identity the accumulator rests on.")
    print("        It does NOT exercise the paper's accumulator implementation, which")
    print("        lives in the RTL/kernel and is a separate claim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
