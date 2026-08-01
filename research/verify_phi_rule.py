#!/usr/bin/env python3
"""Independent check of the central rule of arXiv:2606.05017.

The paper states: for total width N >= 4, the exponent width is
    e = round((N - 1) / phi^2),  f = N - 1 - e,  phi = (1 + sqrt(5)) / 2
and claims it "reproduces the realised exponent widths of nine formats
GF4, GF8, GF12, GF16, GF20, GF24, GF32, GF64, GF256 (9/9)".

This script recomputes the rule from scratch and compares it against the
*catalogued* parameters actually used by the golden oracle
(`conformance/gf_ref.py`, FORMATS) — i.e. against the artefact, not against the
paper's own restatement of it.

Rounding: reported for BOTH conventions (half-even, as Python's round(), and
half-up), because the two differ on an exact .5 and the paper does not say which
it means. If no width lands on an exact .5 the distinction is moot — the script
says so explicitly rather than leaving it implicit.

Run:  python3 research/verify_phi_rule.py
Exit: 0 if every catalogued GF width satisfies the rule, 1 otherwise.
"""
from __future__ import annotations
from decimal import Decimal, getcontext, ROUND_HALF_EVEN, ROUND_HALF_UP
import importlib.util
import os
import sys

getcontext().prec = 60

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GF_REF = os.path.join(REPO, "conformance", "gf_ref.py")

# phi = (1 + sqrt 5)/2 ; phi^2 = (3 + sqrt 5)/2
SQRT5 = Decimal(5).sqrt()
PHI2 = (Decimal(3) + SQRT5) / Decimal(2)

# The nine formats the abstract explicitly claims (9/9).
PAPER_NINE = ["gf4", "gf8", "gf12", "gf16", "gf20", "gf24", "gf32", "gf64", "gf256"]


def rule_e(width: int, mode) -> int:
    return int(((Decimal(width) - 1) / PHI2).quantize(Decimal(1), rounding=mode))


def load_formats():
    spec = importlib.util.spec_from_file_location("gf_ref_probe", GF_REF)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.FORMATS


def main() -> int:
    formats = load_formats()
    rows, mismatches, half_cases = [], [], []

    for name, fmt in formats.items():
        width = int(name[2:])                      # gf16 -> 16
        actual_e = fmt.exp_bits
        actual_m = fmt.mant_bits
        e_even = rule_e(width, ROUND_HALF_EVEN)
        e_up = rule_e(width, ROUND_HALF_UP)
        exact = (Decimal(width) - 1) / PHI2
        frac = exact - int(exact)
        if abs(frac - Decimal("0.5")) < Decimal("1e-30"):
            half_cases.append(name)
        ok_e = (actual_e == e_even) or (actual_e == e_up)
        ok_m = (actual_m == width - 1 - actual_e)
        if not (ok_e and ok_m):
            mismatches.append(name)
        rows.append((name, width, actual_e, actual_m, e_even, e_up, ok_e, ok_m))

    w = max(len(r[0]) for r in rows)
    print(f"{'format':<{w}}  N     e_cat  m_cat  e_rule(HE/HU)  e_ok  m_ok  in_paper_9")
    for name, width, ae, am, ee, eu, oke, okm in rows:
        star = "yes" if name in PAPER_NINE else " - "
        print(f"{name:<{w}}  {width:<4}  {ae:<5}  {am:<5}  {ee:>3}/{eu:<9}  "
              f"{'OK ' if oke else 'BAD'}   {'OK ' if okm else 'BAD'}   {star}")

    print()
    total = len(rows)
    matched = total - len(mismatches)
    print(f"catalogued GF formats satisfying the rule: {matched}/{total}")
    print(f"the abstract claims: {len(PAPER_NINE)}/9 "
          f"({', '.join(PAPER_NINE)})")

    extra = [r[0] for r in rows if r[0] not in PAPER_NINE and r[6] and r[7]]
    if extra:
        print(f"ALSO satisfying the rule but NOT claimed in the abstract "
              f"({len(extra)}): {', '.join(extra)}")

    if half_cases:
        print(f"widths landing on an exact .5 (rounding convention matters): "
              f"{', '.join(half_cases)}")
    else:
        print("no width lands on an exact .5 — half-even and half-up agree "
              "everywhere, so the paper's unstated rounding convention is moot.")

    if mismatches:
        print(f"MISMATCHES: {', '.join(mismatches)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
