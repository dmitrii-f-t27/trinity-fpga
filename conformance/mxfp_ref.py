#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mxfp_ref.py — ЭТАЛОННЫЙ (golden) оракул для OCP MX (Microscaling) блок-масштабируемых
форматов: mxfp4, mxfp6, mxfp8_e4m3, mxint8, mxgf4, mxgf6.

MX-блок = 1 shared scale-байт (e8m0, беззнаковый порядок с bias 127) + N элементов.
Каждый элемент — это мини-формат (sign + exp + mant ИЛИ целое ИЛИ GF-мантисса);
значение элемента = decoded_element * 2^(scale_exp - 127).

Так как scale общий для всего блока, оракул хранит scale_exp в формате (по умолчанию
0, т.е. множитель 2^0 = 1) и применяет его в decode/encode. Scale-aware варианты
(decode_scaled/encode_scaled) позволяют задать экспоненту блока.

Round-ties-even, точная Fraction-арифметика. По образцу gf_ref.py.

Honesty: Trinity conformance team.
"""

from fractions import Fraction
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MXFormat:
    name: str
    elem_bits: int
    kind: str               # 'fp' (minifloat) | 'int' (signed) | 'gf' (no-exp minifloat)
    exp_bits: int = 0
    mant_bits: int = 0
    bias: int = 0
    has_inf: bool = False
    nan_at_max_only: bool = False
    scale_exp: int = 0      # shared e8m0 unbiased block exponent (default 0 -> *2^0)
    # Fractional bits of an integer element. OCP MX v1.0 gives MXINT8 six, so the element
    # value is int * 2^-6. Zero for a format that really is a plain integer.
    int_frac_bits: int = 6

    @property
    def width(self): return self.elem_bits
    @property
    def mask(self): return (1 << self.elem_bits) - 1
    @property
    def sign_shift(self):
        return self.elem_bits - 1
    @property
    def pos_zero(self): return 0
    @property
    def neg_zero(self): return 1 << self.sign_shift
    @property
    def quiet_nan(self):
        # element-level NaN only meaningful for fp/gf minifloats
        em = (1 << self.exp_bits) - 1 if self.exp_bits else 0
        mm = (1 << self.mant_bits) - 1 if self.mant_bits else 1
        if self.has_inf:
            return (em << self.mant_bits) | 1
        if self.nan_at_max_only:
            return (em << self.mant_bits) | mm
        return (em << self.mant_bits) | 1
    @property
    def scale_factor(self):
        return pow2(self.scale_exp)


FORMATS = {
    "mxfp4":     MXFormat("mxfp4",     elem_bits=4, kind='fp', exp_bits=2, mant_bits=1, bias=1),
    "mxfp6":     MXFormat("mxfp6",     elem_bits=6, kind='fp', exp_bits=2, mant_bits=3, bias=1),
    "mxfp8_e4m3":MXFormat("mxfp8_e4m3",elem_bits=8, kind='fp', exp_bits=4, mant_bits=3,
                          bias=7, nan_at_max_only=True),
    "mxint8":    MXFormat("mxint8",    elem_bits=8, kind='int'),
    "mxgf4":     MXFormat("mxgf4",     elem_bits=4, kind='gf', exp_bits=1, mant_bits=2, bias=0),
    "mxgf6":     MXFormat("mxgf6",     elem_bits=6, kind='gf', exp_bits=2, mant_bits=3, bias=1),
}


class Special:
    def __init__(self, kind="nan", sign=0):
        self.kind = kind
        self.sign = sign

    def __repr__(self):
        return "NaN" if self.kind == "nan" else ("-" if self.sign else "+") + "Inf"


def pow2(e: int) -> Fraction:
    if e >= 0:
        return Fraction(1 << e, 1)
    return Fraction(1, 1 << (-e))


def ilog2_floor(a: Fraction) -> int:
    assert a > 0
    n, d = a.numerator, a.denominator
    e = n.bit_length() - d.bit_length()
    if Fraction(n, d) < pow2(e):
        e -= 1
    while Fraction(n, d) >= pow2(e + 1):
        e += 1
    return e


def _round_half_even(x: Fraction, cap=None):
    floor_i = x.numerator // x.denominator
    rem = x - floor_i
    half = Fraction(1, 2)
    if rem < half:
        r = floor_i
    elif rem > half:
        r = floor_i + 1
    else:
        r = floor_i if (floor_i % 2 == 0) else floor_i + 1
    if cap is not None and r >= cap:
        return cap, True
    return r, False


# -------------------- element-level decode/encode --------------------

def _decode_elem(fmt: MXFormat, raw: int):
    """Decode the element WITHOUT block scale. Returns Fraction | Special."""
    raw &= fmt.mask
    if fmt.kind == 'int':
        # OCP Microscaling Formats v1.0 defines MXINT8 as a two's-complement int8 with an
        # implied binary point six places in -- the element value is int * 2^-6, giving a
        # range of +-127/64 -- and reserves -128. This module returned the raw integer, so
        # 0x01 was 1 where the format says 1/64 and 0x80 was -128 where the format says
        # nothing at all.
        #
        # conformance/mxint8_decode_conformance_ax7203.py has stated the correct
        # convention in its own header since it was written -- "int8 x 2^-6 -> FP32
        # (range +/-127/64). -128 reserved -> NaN" -- and the RTL follows it. Pass 211
        # counted the two sides as diverging on 455 of 456 codes; it is one difference,
        # and this side was the wrong one.
        if raw == (1 << fmt.sign_shift):
            return Special("nan")                    # -128 is reserved
        v = raw - (1 << fmt.elem_bits) if raw >> fmt.sign_shift else raw
        return Fraction(v, 1 << fmt.int_frac_bits)

    sign = (raw >> fmt.sign_shift) & 1
    exp = (raw >> fmt.mant_bits) & ((1 << fmt.exp_bits) - 1)
    mant = raw & ((1 << fmt.mant_bits) - 1)
    emax = (1 << fmt.exp_bits) - 1
    mmax = (1 << fmt.mant_bits) - 1

    if fmt.kind in ('fp', 'gf'):
        if exp == emax:
            if fmt.has_inf:
                return Special("inf", sign) if mant == 0 else Special("nan")
            if fmt.nan_at_max_only and mant == mmax:
                return Special("nan")
        if exp == 0:
            if mant == 0:
                return Fraction(0)
            val = Fraction(mant, 1 << fmt.mant_bits) * pow2(1 - fmt.bias)
        else:
            val = (1 + Fraction(mant, 1 << fmt.mant_bits)) * pow2(exp - fmt.bias)
        return -val if sign else val
    raise ValueError(fmt.kind)


def _encode_elem(fmt: MXFormat, value):
    """Encode value (WITHOUT block scale) -> element raw, RNE."""
    if isinstance(value, Special):
        if fmt.kind == 'int':
            return 0
        return fmt.quiet_nan

    v = Fraction(value)
    if fmt.kind == 'int':
        m, _ = _round_half_even(v * (1 << fmt.int_frac_bits))
        # saturate to signed range
        hi = (1 << (fmt.elem_bits - 1)) - 1
        lo = -(1 << (fmt.elem_bits - 1))
        if m > hi:
            m = hi
        elif m < lo:
            m = lo
        return m & fmt.mask

    if v == 0:
        return fmt.pos_zero
    sign = 1 if v < 0 else 0
    a = -v if v < 0 else v
    E = ilog2_floor(a)
    exp_field = E + fmt.bias
    emax = (1 << fmt.exp_bits) - 1
    mmax = (1 << fmt.mant_bits) - 1

    if exp_field >= 1:
        frac = a / pow2(E) - 1
        mant, carry = _round_half_even(frac * (1 << fmt.mant_bits), cap=(1 << fmt.mant_bits))
        if carry:
            mant = 0
            exp_field += 1
        if fmt.has_inf and exp_field >= emax:
            return ((1 << fmt.sign_shift) | (emax << fmt.mant_bits)) if sign else (emax << fmt.mant_bits)
        if fmt.nan_at_max_only and (exp_field > emax or (exp_field == emax and mant >= mmax)):
            sat = (emax << fmt.mant_bits) | (mmax - 1)
            return ((1 << fmt.sign_shift) | sat) if sign else sat
        if (not fmt.has_inf and not fmt.nan_at_max_only) and exp_field > emax:
            sat = (emax << fmt.mant_bits) | mmax
            return ((1 << fmt.sign_shift) | sat) if sign else sat
        return (sign << fmt.sign_shift) | (exp_field << fmt.mant_bits) | (mant & mmax)
    else:
        scale = pow2(1 - fmt.bias)
        m_real = a / scale * (1 << fmt.mant_bits)
        m, _ = _round_half_even(m_real)
        if m == 0:
            return (sign << fmt.sign_shift)
        if m > mmax:
            return (sign << fmt.sign_shift) | (1 << fmt.mant_bits)
        return (sign << fmt.sign_shift) | (m & mmax)


# -------------------- block-scaled decode/encode --------------------

def decode(fmt: MXFormat, raw: int):
    e = _decode_elem(fmt, raw)
    if isinstance(e, Special):
        return e
    return e * fmt.scale_factor


def decode_scaled(fmt: MXFormat, raw: int, scale_exp: int):
    e = _decode_elem(fmt, raw)
    if isinstance(e, Special):
        return e
    return e * pow2(scale_exp)


def encode(fmt: MXFormat, value):
    if isinstance(value, Special):
        return _encode_elem(fmt, value)
    v = Fraction(value)
    return _encode_elem(fmt, v / fmt.scale_factor)


def encode_scaled(fmt: MXFormat, value, scale_exp: int):
    if isinstance(value, Special):
        return _encode_elem(fmt, value)
    v = Fraction(value)
    return _encode_elem(fmt, v / pow2(scale_exp))


def format_add(fmt: MXFormat, a_raw: int, b_raw: int) -> int:
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    if isinstance(a, Special) or isinstance(b, Special):
        return fmt.quiet_nan if fmt.kind != 'int' else 0
    if a == 0 and b == 0:
        return fmt.pos_zero
    return encode(fmt, a + b)


def format_mul(fmt: MXFormat, a_raw: int, b_raw: int) -> int:
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    if isinstance(a, Special) or isinstance(b, Special):
        return fmt.quiet_nan if fmt.kind != 'int' else 0
    sa = (a_raw >> fmt.sign_shift) & 1
    sb = (b_raw >> fmt.sign_shift) & 1
    rsign = sa ^ sb
    if a == 0 or b == 0:
        return fmt.neg_zero if rsign else fmt.pos_zero
    return encode(fmt, a * b)


def _selftest():
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    for fname, fmt in FORMATS.items():
        check(decode(fmt, 0) == 0, f"{fname}: +0")
        check(encode(fmt, 0) == 0, f"{fname}: encode 0")

        if fmt.kind != 'int':
            one = encode(fmt, Fraction(1))
            check(decode(fmt, one) == 1, f"{fname}: unity (0x{one:x})")
            r = format_add(fmt, one, one)
            check(decode(fmt, r) == 2, f"{fname}: 1+1=2 (got {decode(fmt, r)})")
        else:
            # mxint8: 1 + 1 SATURATES. OCP MX v1.0 gives the format an implied binary
            # point six places in, so its range is +-127/64 and 2 is not in it. The
            # assertion here was `1+1=2`, which held only under the plain-integer reading
            # this module used before -- a check encoding the convention it was meant to
            # be testing.
            one = encode(fmt, Fraction(1))
            check(decode(fmt, one) == 1, f"{fname}: 1 (0x{one:x})")
            r = format_add(fmt, one, one)
            check(decode(fmt, r) == Fraction(127, 64),
                  f"{fname}: 1+1 saturates to 127/64, the largest value the format has")
            check(isinstance(decode(fmt, 0x80), Special),
                  f"{fname}: 0x80 is reserved")

        check(format_add(fmt, 0, 0) == 0, f"{fname}: 0+0=0")

        # block scale check: scale_exp=3 multiplies by 8
        if fmt.kind != 'int':
            scaled = decode_scaled(fmt, one, 3)
            check(scaled == 8, f"{fname}: scale_exp=3 -> *8 (got {scaled})")

        # x + 0 == x bit-exact (exhaustive for small, sampled for mxint8/mxfp8)
        codes = range(0, 1 << fmt.elem_bits)
        for raw in codes:
            v = decode(fmt, raw)
            if isinstance(v, Special) or v == 0:
                continue
            check(format_add(fmt, raw, 0) == raw, f"{fname}: x+0!=x 0x{raw:x}")

    if failures:
        print("SELF-TEST: FAIL (%d)" % len(failures))
        for f in failures[:20]:
            print("  " + f)
        return 1
    print("SELF-TEST: PASS (mxfp: zero/unity/1+1/scale/x+0)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
