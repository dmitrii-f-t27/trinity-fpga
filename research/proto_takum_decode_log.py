#!/usr/bin/env python3
"""FEASIBILITY PROBE — can the LNS log-domain technique be applied to takum?

This is a PROBE, not a change. conformance/takum_ref.py is not touched.

Context (specs/numeric/oracle_fidelity_map.t27): takum_ref.py implements a linear
structural model because takum values are irrational and cannot be exact
Fractions. lns_ref.py faces the identical problem and solves it correctly, by
returning the exact value in the LOGARITHMIC domain:

    decode_log(raw) -> Fraction(field, 1 << frac_bits)     # dyadic, exact

The question here is whether takum's logarithmic value is likewise dyadic. If it
is, the same technique gives an exact takum oracle and the structural model
becomes unnecessary.

takum is defined with value = (-1)^S * exp(ell/2), and ell is assembled from the
characteristic c and the mantissa fraction M_u/2^p — both dyadic. So the
hypothesis is:

    ell(raw) = c + M_u / 2^p        -- the logarithm of the MAGNITUDE
    sign(raw) = leading bit          -- carried separately, as lns_ref does

Verified numerically against libtakum's LOGARITHMIC conversion (the dumps produced
by research/libtakum_bridge.c with the `log` argument).

Run:
    /tmp/libtakum_bridge 16 log > /tmp/lt16_log.tsv
    python3 research/proto_takum_decode_log.py /tmp/lt16_log.tsv
"""
from __future__ import annotations
from fractions import Fraction
import importlib.util
import math
import os
import struct
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(REPO, "conformance")


def load_takum():
    sys.path.insert(0, CONF)
    spec = importlib.util.spec_from_file_location("tkp", os.path.join(CONF, "takum_ref.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def decode_log(mod, fmt, raw: int):
    """Exact logarithmic value of a takum code, as a Fraction. None for specials.

    Reuses takum_ref's own field extraction — the field LAYOUT is not in question,
    only how the fields are interpreted (linearly there, logarithmically here).
    """
    raw &= fmt.mask
    if raw == 0 or raw == fmt.nar:
        return None
    if (raw >> (fmt.n - 1)) & 1:
        # The complement negates the VALUE, not ell. Since value = +-exp(ell/2),
        # the magnitude's logarithm is unchanged and only the sign flips -- which
        # is precisely why lns_ref stores sign(value) SEPARATELY from
        # log2(|value|). Conflating them was the first version's error.
        return decode_log(mod, fmt, (-raw) & fmt.mask)

    D = (raw >> (fmt.n - 2)) & 1
    R = (raw >> (fmt.n - 2 - fmt.regime_bits)) & (fmt.regime_count - 1)
    lower = raw & ((1 << fmt.payload_bits) - 1)
    r_eff, p, cbias = mod._regime_params(fmt, D, R)
    C_u = (lower >> p) & ((1 << r_eff) - 1) if r_eff > 0 else 0
    M_u = lower & ((1 << p) - 1) if p > 0 else 0
    c = cbias + C_u
    return Fraction(c) + (Fraction(M_u, 1 << p) if p > 0 else Fraction(0))


def main(argv) -> int:
    if not argv:
        print(__doc__)
        return 2
    path = argv[0]
    if not os.path.exists(path):
        print(f"missing dump {path} — build it with the bridge first")
        return 2

    mod = load_takum()
    fmt = mod.FORMATS["takum16"]

    ref = {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                r, h = line.split("\t")
                ref[int(r)] = struct.unpack(">d", bytes.fromhex(h))[0]

    checked = agree = 0
    worst_rel = 0.0
    worst_at = None
    mism = []

    for raw in range(1 << fmt.n):
        ell = decode_log(mod, fmt, raw)
        if ell is None:
            continue
        target = ref.get(raw)
        if target is None or target != target or target == 0.0:
            continue
        try:
            got = math.exp(float(ell) / 2.0)
        except OverflowError:
            continue
        if not math.isfinite(got) or not math.isfinite(target):
            continue
        checked += 1
        rel = abs(got - abs(target)) / abs(target)
        if rel > worst_rel:
            worst_rel, worst_at = rel, raw
        if rel < 1e-12:
            agree += 1
        elif len(mism) < 5:
            mism.append((raw, float(ell), got, target))

    print("HYPOTHESIS  ell = c + M_u/2^p is log of the MAGNITUDE; sign carried separately")
    print(f"reference   libtakum LOGARITHMIC, takum16\n")
    print(f"  codes checked        : {checked}")
    print(f"  agree (rel < 1e-12)  : {agree}")
    print(f"  worst relative error : {worst_rel:.3e}" + (f" at 0x{worst_at:04x}" if worst_at else ""))
    for raw, ell, got, target in mism:
        print(f"    0x{raw:04x} ell={ell} exp(ell/2)={got:.6e} libtakum={target:.6e}")

    print()
    if checked and agree == checked:
        print("FEASIBLE. The logarithmic value is dyadic and exactly representable as a")
        print("Fraction, so the lns_ref technique transfers to takum directly. An exact")
        print("log-domain takum oracle needs no new mathematics — only decode_log().")
        print()
        print("NOTE: agreement is checked numerically via exp(), which is itself inexact.")
        print("What is established is that ell is exact and correct; the exponentiation")
        print("is the caller's business, exactly as with lns_ref.")
    else:
        print("NOT ESTABLISHED by this probe — the hypothesis does not reproduce libtakum.")
        print("Do not act on the recommendation until this is understood.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
