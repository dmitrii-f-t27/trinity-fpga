#!/usr/bin/env python3
"""Settle why decimal32/64 are flagged non-monotonic in code order.

verify_intrinsic_invariants.py reports 192 and 241 monotonicity violations over a
4000-code sample of the positive half. Its own header says a flag is a lead, not a
verdict.

Pass 56 attempted this twice and both attempts were void. Each grouped codes by the
NORMALISED power of ten in the decoded value -- for instance 832006 and 468322 both
normalise to 10^0 -- which is not the stored exponent, so neither test measured what
it claimed to. The numbers they produced were artefacts of the grouping.

This uses the STORED fields. decimal_ref._bid_decode returns (sign, C, E_field)
straight from the encoding, so codes can be grouped by the exponent actually stored
rather than by one inferred from the value.

The prediction is sharp. Inside a fixed stored exponent, value = C * 10^(E - bias),
so value order is exactly C order; and C occupies the low bits of the code, so code
order is C order too. Monotonicity within a group must therefore hold EXACTLY, and
every violation must sit at a boundary where E changes.

If a violation turns up inside a group, this explanation is wrong and that code is
the interesting one.

Run:  python3 research/verify_decimal_monotonic.py
Exit: 0 if every violation is a stored-exponent change, 1 if any is not.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from fractions import Fraction

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(REPO, "conformance")
SAMPLE = 4000


def load():
    sys.path.insert(0, CONF)
    spec = importlib.util.spec_from_file_location(
        "decimal_ref", os.path.join(CONF, "decimal_ref.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    mod = load()
    print(f"{'format':<12}{'sampled':>9}{'violations':>12}"
          f"{'at E change':>13}{'inside a group':>16}")
    print("-" * 62)

    bad_inside_total = 0
    for name in ("decimal32", "decimal64", "decimal128"):
        fmt = mod.FORMATS.get(name)
        if fmt is None:
            print(f"{name:<12}  not exported")
            continue

        half = 1 << fmt.sign_shift          # positive half: sign bit clear
        step = max(1, half // SAMPLE)

        prev_val = None
        prev_E = None
        n = viol = at_E_change = inside = 0
        examples = []

        for raw in range(0, half, step):
            fields = mod._bid_decode(fmt, raw)
            if fields[0] != "finite":
                continue
            _, _, C, E = fields
            # Ask the oracle, do not infer from C. This guard used to read
            # `C > fmt.max_coeff`, which worked only while the decoder handed back the
            # oversized coefficient. Pass 185 made _bid_decode obey IEEE 754-2008 3.5.2
            # and return zero for exactly these codes, so the condition became
            # unsatisfiable and 174 of them swept through as genuine zeros -- reported
            # here as monotonicity violations that were nothing of the sort.
            if not mod.is_canonical(fmt, raw):   # non-canonical: no value is defined
                continue
            val = Fraction(C) * Fraction(10) ** (E - fmt.bias)
            n += 1

            if prev_val is not None and val <= prev_val:
                viol += 1
                if E != prev_E:
                    at_E_change += 1
                else:
                    inside += 1
                    if len(examples) < 3:
                        examples.append((hex(raw), E, C, str(val)[:20]))
            prev_val, prev_E = val, E

        bad_inside_total += inside
        print(f"{name:<12}{n:>9}{viol:>12}{at_E_change:>13}{inside:>16}")
        for h, E, C, v in examples:
            print(f"        UNEXPLAINED inside E={E}: code {h} C={C} value {v}")

    print()
    if bad_inside_total == 0:
        print("Every violation coincides with a change of the STORED exponent field.")
        print("Within one exponent, code order and value order agree exactly, because")
        print("the coefficient occupies the low bits and value = C * 10^(E - bias).")
        print()
        print("So the flag records a property of BID -- the combination field puts")
        print("exponent bits above coefficient bits, so sweeping codes upward does not")
        print("sweep values upward. It is why decimal comparison requires decoding,")
        print("and it is not a defect in the oracle.")
    else:
        print(f"{bad_inside_total} violation(s) occur INSIDE a fixed stored exponent.")
        print("That contradicts the encoding's own structure -- investigate those codes.")
    return 1 if bad_inside_total else 0


if __name__ == "__main__":
    raise SystemExit(main())
