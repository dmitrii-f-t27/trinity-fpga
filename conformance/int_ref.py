#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
int_ref.py — ЭТАЛОННЫЙ (golden) оракул для целочисленных форматов.
  int4, int8, int16, int32, int64, int128    — two's complement signed
  uint4, uint8, uint16, uint32               — unsigned

Целые числа точно представимы как Fraction. Арифметика — modular (wraparound)
по умолчанию (стандартное поведение fixed-width int); есть также saturating-варианты.
По образцу gf_ref.py.

Honesty: Trinity conformance team.
"""

from fractions import Fraction
from dataclasses import dataclass


@dataclass(frozen=True)
class IntFormat:
    name: str
    bits: int
    signed: bool

    @property
    def mask(self): return (1 << self.bits) - 1
    @property
    def width(self): return self.bits
    @property
    def sign_shift(self): return self.bits - 1
    @property
    def max_val(self):
        return (1 << (self.bits - 1)) - 1 if self.signed else self.mask
    @property
    def min_val(self):
        return -(1 << (self.bits - 1)) if self.signed else 0
    @property
    def pos_zero(self): return 0
    @property
    def quiet_nan(self): return 0   # ints have no NaN


FORMATS = {
    "int4":   IntFormat("int4",   bits=4,   signed=True),
    "int8":   IntFormat("int8",   bits=8,   signed=True),
    "int16":  IntFormat("int16",  bits=16,  signed=True),
    "int32":  IntFormat("int32",  bits=32,  signed=True),
    "int64":  IntFormat("int64",  bits=64,  signed=True),
    "int128": IntFormat("int128", bits=128, signed=True),
    "uint4":  IntFormat("uint4",  bits=4,   signed=False),
    "uint8":  IntFormat("uint8",  bits=8,   signed=False),
    "uint16": IntFormat("uint16", bits=16,  signed=False),
    "uint32": IntFormat("uint32", bits=32,  signed=False),
}


def pow2(e: int) -> Fraction:
    if e >= 0:
        return Fraction(1 << e, 1)
    return Fraction(1, 1 << (-e))


def decode(fmt: IntFormat, raw: int) -> Fraction:
    """raw -> exact integer value as Fraction."""
    raw &= fmt.mask
    if fmt.signed and (raw >> fmt.sign_shift):
        return Fraction(raw - (1 << fmt.bits))
    return Fraction(raw)


def encode(fmt: IntFormat, value) -> int:
    """Exact integer -> raw (two's complement for signed). Out-of-range wraps (modular)."""
    v = Fraction(value)
    assert v.denominator == 1, "int encode requires integer value"
    n = v.numerator
    return n & fmt.mask


def encode_saturating(fmt: IntFormat, value) -> int:
    """Saturating variant: clamp to [min_val, max_val]."""
    v = Fraction(value)
    assert v.denominator == 1
    n = v.numerator
    if n < fmt.min_val:
        n = fmt.min_val
    elif n > fmt.max_val:
        n = fmt.max_val
    return n & fmt.mask


def format_add(fmt: IntFormat, a_raw: int, b_raw: int) -> int:
    """Modular (wraparound) addition."""
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    return encode(fmt, a + b)


def format_mul(fmt: IntFormat, a_raw: int, b_raw: int) -> int:
    """Modular (wraparound) multiplication."""
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    return encode(fmt, a * b)


def format_add_sat(fmt: IntFormat, a_raw: int, b_raw: int) -> int:
    """Saturating addition."""
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    return encode_saturating(fmt, a + b)


def format_mul_sat(fmt: IntFormat, a_raw: int, b_raw: int) -> int:
    """Saturating multiplication."""
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    return encode_saturating(fmt, a * b)


def _selftest():
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    for fname, fmt in FORMATS.items():
        check(decode(fmt, 0) == 0, f"{fname}: 0")
        check(encode(fmt, 0) == 0, f"{fname}: encode 0")
        one = encode(fmt, 1)
        check(decode(fmt, one) == 1, f"{fname}: 1")
        # 1 + 1 = 2
        r = format_add(fmt, one, one)
        check(decode(fmt, r) == 2, f"{fname}: 1+1=2 (got {decode(fmt, r)})")
        # 0 + 0 = 0
        check(format_add(fmt, 0, 0) == 0, f"{fname}: 0+0=0")
        # x + 0 == x (bit-exact for all x): exhaustive for tiny, sampled otherwise
        if fmt.bits <= 16:
            check_range = range(0, 1 << fmt.bits)
        else:
            rng = __import__("random").Random(0x1337 + fmt.bits)
            check_range = [rng.randrange(1 << fmt.bits) for _ in range(8000)]
        for raw in check_range:
            check(format_add(fmt, raw, 0) == raw, f"{fname}: x+0!=x 0x{raw:x}")
        # identity: x * 1 == x
        check(format_mul(fmt, one, one) == one, f"{fname}: 1*1=1")
        # wraparound at boundary
        check(decode(fmt, encode(fmt, fmt.max_val)) == fmt.max_val, f"{fname}: max round-trip")
        if fmt.signed:
            check(decode(fmt, encode(fmt, fmt.min_val)) == fmt.min_val, f"{fname}: min round-trip")
            # max + 1 wraps to min
            mx = encode(fmt, fmt.max_val)
            check(decode(fmt, format_add(fmt, mx, one)) == fmt.min_val,
                  f"{fname}: max+1 wraps to min")
        else:
            # unsigned: max + 1 wraps to 0
            mx = encode(fmt, fmt.max_val)
            check(format_add(fmt, mx, one) == 0, f"{fname}: max+1 wraps to 0")

    # specific signed/int8 checks
    i8 = FORMATS["int8"]
    check(decode(i8, 0xFF) == -1, "int8: 0xFF -> -1")
    check(decode(i8, 0x80) == -128, "int8: 0x80 -> -128")
    check(decode(i8, 0x7F) == 127, "int8: 0x7F -> 127")
    check(decode(i8, format_add(i8, encode(i8, -1), encode(i8, 1))) == 0, "int8: -1+1=0")
    u4 = FORMATS["uint4"]
    check(decode(u4, 0xF) == 15, "uint4: 0xF -> 15")

    if failures:
        print("SELF-TEST: FAIL (%d)" % len(failures))
        for f in failures[:20]:
            print("  " + f)
        return 1
    print("SELF-TEST: PASS (int: zero/unity/1+1/x+0/x*1/wraparound/boundaries)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
