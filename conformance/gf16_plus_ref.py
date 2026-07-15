#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gf16_plus_ref.py — ЭТАЛОННЫЙ (golden) оракул для GF16+ (GoldenFloat16+).

GF16+ = GF16 storage format + binary64 Quire accumulation:
  - Операнды хранятся в GF16 (E=6, M=9, BIAS=31, HAS_INF=1).
  - Умножение выполняется в GF16 (с округлением RNE — как gf_mul_param).
  - Произведение добавляется в Quire (binary64 / IEEE-754 double, точное для
    малых сумм).
  - FLUSH: округляет binary64-аккумулятор обратно в GF16 (RNE ties-even) и сбрасывает его.

Статус: [смоделировано] — это SW-оракул. HW-проверка закрывается отдельным
bit-exact прогоном на AX7203 (conformance/gf16_plus_*_conformance_ax7203.py).

Honesty: Vasilev, ORCID 0009-0008-4294-6159.
"""

import math
from fractions import Fraction

from gf_ref import FORMATS, decode, encode, gf_mul, Special

# GF16 format: [S:1][E:6][M:9], BIAS=31, HAS_INF=1
GF16 = FORMATS["gf16"]

OP_MAC, OP_MACSUB, OP_FLUSH = 0, 1, 2


# -------------------- GF16 <-> binary64 helpers --------------------

def gf16_to_binary64(raw):
    """Decode GF16 raw -> Python float (binary64). Inf/NaN mapped to float specials."""
    v = decode(GF16, raw)
    if isinstance(v, Special):
        if v.kind == "nan":
            return float("nan")
        return float("-inf") if v.sign else float("inf")
    return float(v)


def binary64_to_gf16(x):
    """Round a binary64 (Python float) value to GF16 raw (RNE ties-even via exact Fraction)."""
    if math.isnan(x):
        return GF16.quiet_nan
    if math.isinf(x):
        return GF16.neg_inf if x < 0 else GF16.pos_inf
    if x == 0.0:
        # preserve sign of zero: -0.0 -> neg_zero, +0.0 -> pos_zero
        return GF16.neg_zero if math.copysign(1.0, x) < 0 else GF16.pos_zero
    return encode(GF16, Fraction(x))


# -------------------- GF16+ MAC --------------------

def gf16_plus_mac(state, a_raw, b_raw, op):
    """
    One GF16+ operation.

    Args:
        state:  current Quire value (binary64 float, 0.0 after reset/flush)
        a_raw:  GF16 raw operand A
        b_raw:  GF16 raw operand B
        op:     OP_MAC (0) | OP_MACSUB (1) | OP_FLUSH (2)

    Returns:
        (new_state, flush_result_raw | None)
          - MAC/MACSUB: (new_state, None)     -- no GF16 output produced
          - FLUSH:      (0.0, gf16_raw)       -- accumulator read & reset

    The GF16 product is computed first (RNE, exactly mirroring gf_mul_param), then
    decoded to binary64 and accumulated into the Quire. On FLUSH the binary64
    accumulator is rounded back to GF16.
    """
    # Stage 1: GF16 multiply (rounds product to GF16, as the HW mul does)
    prod_raw = gf_mul(GF16, a_raw, b_raw)
    prod = gf16_to_binary64(prod_raw)

    if op == OP_MAC:
        return (state + prod, None)
    if op == OP_MACSUB:
        return (state - prod, None)
    if op == OP_FLUSH:
        flushed_raw = binary64_to_gf16(state)
        return (0.0, flushed_raw)
    raise ValueError(f"unknown op {op}")


def gf16_plus_flush(state):
    """Read+reset the Quire: rounds binary64 state to GF16 raw. Convenience wrapper."""
    return binary64_to_gf16(state)


# -------------------- SELF-TEST --------------------

def _one_raw():
    """GF16 raw for +1.0 = (0, exp=BIAS=31, mant=0) = 31 << 9."""
    return GF16.bias << GF16.mant_bits


def _selftest():
    # --- Test 1: MAC 1.0 * 1.0 three times -> flush -> 3.0 ---
    one = _one_raw()
    assert gf16_to_binary64(one) == 1.0, "GF16 1.0 decode failed"

    state = 0.0
    for _ in range(3):
        state, out = gf16_plus_mac(state, one, one, OP_MAC)
        assert out is None, "MAC must not produce output"
    assert state == 3.0, f"expected state 3.0, got {state}"

    state, out = gf16_plus_mac(state, one, one, OP_FLUSH)
    assert state == 0.0, "FLUSH must reset the Quire"
    expected_3 = binary64_to_gf16(3.0)
    assert out == expected_3, f"flush result {out:#06x} != expected {expected_3:#06x}"
    assert gf16_to_binary64(out) == 3.0, f"flush result decodes to {gf16_to_binary64(out)} != 3.0"

    # --- Test 2: MAC then MACSUB -> flush -> ~0 ---
    state = 0.0
    state, _ = gf16_plus_mac(state, one, one, OP_MAC)      # +1.0
    state, _ = gf16_plus_mac(state, one, one, OP_MACSUB)   # -1.0
    assert state == 0.0, f"1.0 - 1.0 should be 0.0, got {state}"
    state, out = gf16_plus_mac(state, one, one, OP_FLUSH)
    assert out == GF16.pos_zero, f"flush of 0.0 -> {out:#06x}"

    # --- Test 3: 2.0 * 3.0 -> flush -> 6.0 ---
    two_raw = gf_mul(GF16, one, one)            # 1*1 = 1, reuse for structure
    # encode 2.0 and 3.0 directly
    two_raw = encode(GF16, Fraction(2))
    three_raw = encode(GF16, Fraction(3))
    state, _ = gf16_plus_mac(0.0, two_raw, three_raw, OP_MAC)   # 2*3 = 6
    assert state == 6.0, f"2*3 should be 6.0, got {state}"
    state, out = gf16_plus_mac(state, one, one, OP_FLUSH)
    assert gf16_to_binary64(out) == 6.0, f"flush 6.0 -> {gf16_to_binary64(out)}"

    # --- Test 4: flush of empty Quire -> +0 ---
    _, out = gf16_plus_mac(0.0, one, one, OP_FLUSH)
    assert out == GF16.pos_zero, f"empty flush -> {out:#06x}"

    print(f"SELF-TEST: PASS  (3x1.0 flush = {gf16_to_binary64(out) and 3.0}; "
          f"MAC/MACSUB/FLUSH ops OK)")


if __name__ == "__main__":
    _selftest()
