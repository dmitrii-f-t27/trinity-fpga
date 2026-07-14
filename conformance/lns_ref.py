#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lns_ref.py — ЭТАЛОННЫЙ (golden) оракул для Logarithmic Number System (LNS).
  lns8, lns16, lns32, lns64

ВАЖНО О ПРИРОДЕ LNS:
  LNS хранит sign(value) + log2(|value|) как fixed-point. Само значение
  value = (-1)^sign * 2^L в общем случае ИРРАЦИОНАЛЬНО (2^(p/q) для q>1),
  поэтому его НЕЛЬЗЯ представить точно как fractions.Fraction. Это та же
  фундаментальная ситуация, что и у takum (логарифмический формат).

  Поэтому оракул работает В ЛОГАРИФМИЧЕСКОЙ ОБЛАСТИ (точно):
    * decode_log(raw) -> точный log2(|value|) как Fraction (хранимое поле — диадическое).
    * decode(raw)      -> Fraction: возвращает ТОЧНОЕ ЗНАЧЕНИЕ 2^L, когда L целое
                          (степени двойки — естественные "опорные" точки LNS);
                          иначе возвращает Special('irrational') с хранимым логом.
    * format_mul       -> ТОЧНО: log_a + log_b (сложение Fraction), затем RNE-округление.
    * format_add       -> log_a + log2(1 + 2^(log_b - log_a)); трансцендентный шаг
                          считается в double precision math (достаточно для lns8/16/32;
                          для lns64 — приближение, что задокументировано).

Кодировка:
  bit[width-1]        = sign(value)
  bits[width-2:0]     = signed two's-complement log field, `frac_bits` дробных бит
  field == field_min (most negative) -> flush-to-zero (value 0; LNS не имеет log(0)).

Honesty: Trinity conformance team.
"""

from fractions import Fraction
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class LNSFormat:
    name: str
    width: int
    frac_bits: int

    @property
    def field_bits(self): return self.width - 1
    @property
    def field_min(self): return -(1 << (self.field_bits - 1))
    @property
    def field_max(self): return (1 << (self.field_bits - 1)) - 1
    @property
    def mask(self): return (1 << self.width) - 1
    @property
    def sign_shift(self): return self.width - 1
    @property
    def field_mask(self): return (1 << self.field_bits) - 1
    @property
    def pos_zero(self): return self.field_min & self.field_mask   # sign 0, field = most-negative
    @property
    def nar(self): return (1 << self.sign_shift) | (self.field_min & self.field_mask)


FORMATS = {
    "lns8":  LNSFormat("lns8",  width=8,  frac_bits=3),
    "lns16": LNSFormat("lns16", width=16, frac_bits=8),
    "lns32": LNSFormat("lns32", width=32, frac_bits=16),
    "lns64": LNSFormat("lns64", width=64, frac_bits=32),
}


class Special:
    """Для LNS: 'zero' (underflow), 'nar', или 'irrational' (2^L не представимо как Fraction)."""

    def __init__(self, kind="nar", sign=0, log=None):
        self.kind = kind
        self.sign = sign
        self.log = log   # точный log2(|value|) как Fraction, для 'irrational'

    def __repr__(self):
        if self.kind == "zero":
            return "0"
        if self.kind == "nar":
            return "NaR"
        if self.kind == "irrational":
            return ("-" if self.sign else "+") + f"2^({self.log})"
        return self.kind


def pow2(e: int) -> Fraction:
    if e >= 0:
        return Fraction(1 << e, 1)
    return Fraction(1, 1 << (-e))


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


# -------------------- decode --------------------

def decode_log(fmt: LNSFormat, raw: int):
    """Точный log2(|value|) как Fraction, или Special('zero'/'nar')."""
    raw &= fmt.mask
    if raw == fmt.nar:
        return Special("nar")
    field_unsigned = raw & ((1 << fmt.field_bits) - 1)
    # two's complement sign-extend
    if field_unsigned >> (fmt.field_bits - 1):
        field = field_unsigned - (1 << fmt.field_bits)
    else:
        field = field_unsigned
    if field == fmt.field_min:
        return Special("zero")
    return Fraction(field, 1 << fmt.frac_bits)


def sign_of(fmt: LNSFormat, raw: int) -> int:
    return (raw >> fmt.sign_shift) & 1


def decode(fmt: LNSFormat, raw: int):
    """value как Fraction, когда log целое (степень двойки); иначе Special('irrational')."""
    raw &= fmt.mask
    if raw == fmt.nar:
        return Special("nar")
    sign = sign_of(fmt, raw)
    lg = decode_log(fmt, raw)
    if isinstance(lg, Special):
        return Fraction(0) if lg.kind == "zero" else lg
    # 2^lg точно как Fraction только когда lg — целое
    if lg.denominator == 1:
        e = lg.numerator
        val = pow2(e)
        return -val if sign else val
    return Special("irrational", sign, lg)


def value_of(fmt: LNSFormat, raw: int) -> float:
    """Приблизительное значение как float (для отладки/отображения)."""
    sign = sign_of(fmt, raw)
    lg = decode_log(fmt, raw)
    if isinstance(lg, Special):
        return float('nan') if lg.kind == "nar" else 0.0
    e = float(lg)
    mag = 2.0 ** e
    return -mag if sign else mag


# -------------------- encode --------------------

def encode_from_log(fmt: LNSFormat, sign: int, log_value: Fraction) -> int:
    """Упаковать (sign, log2|value|) с RNE к frac_bits дробным битам."""
    if fmt.nar is not None and False:
        pass
    scaled = log_value * (1 << fmt.frac_bits)
    field, carry = _round_half_even(scaled)
    # clamp into representable range; field_min reserved for zero/underflow
    lo = fmt.field_min + 1
    hi = fmt.field_max
    if field < lo:
        # underflow -> zero
        return fmt.pos_zero
    if field > hi:
        field = hi
    field &= ((1 << fmt.field_bits) - 1)
    return ((sign & 1) << fmt.sign_shift) | field


def encode(fmt: LNSFormat, value) -> int:
    """Encode из Fraction|Special. Для не-степеней-двойки использует log2 через math
    (приближение); предпочтительно использовать encode_from_log для точности."""
    if isinstance(value, Special):
        if value.kind == "nar":
            return fmt.nar
        return fmt.pos_zero
    v = Fraction(value)
    if v == 0:
        return fmt.pos_zero
    sign = 1 if v < 0 else 0
    a = -v if v < 0 else v
    # log2(a): если a — степень двойки, точно; иначе через ln
    n, d = a.numerator, a.denominator
    # reduce to 2^k * (n'/d'); if n'/d' == 1, exact
    def factors2(x):
        k = 0
        while x > 1 and x % 2 == 0:
            x //= 2
            k += 1
        return k, x
    kn, nn = factors2(n)
    kd, dd = factors2(d)
    if nn == 1 and dd == 1:
        log_value = Fraction(kn - kd, 1)
    else:
        log_value = Fraction(math.log2(float(a))).limit_denominator(1 << fmt.frac_bits)
    return encode_from_log(fmt, sign, log_value)


# -------------------- add / mul (log domain) --------------------

def format_mul(fmt: LNSFormat, a_raw: int, b_raw: int) -> int:
    la = decode_log(fmt, a_raw)
    lb = decode_log(fmt, b_raw)
    sa = sign_of(fmt, a_raw)
    sb = sign_of(fmt, b_raw)
    rsign = sa ^ sb
    if isinstance(la, Special) and la.kind == "nar": return fmt.nar
    if isinstance(lb, Special) and lb.kind == "nar": return fmt.nar
    if (isinstance(la, Special) and la.kind == "zero") or \
       (isinstance(lb, Special) and lb.kind == "zero"):
        return fmt.pos_zero
    # точное сложение логов (Fraction)
    return encode_from_log(fmt, rsign, la + lb)


def format_add(fmt: LNSFormat, a_raw: int, b_raw: int) -> int:
    la = decode_log(fmt, a_raw)
    lb = decode_log(fmt, b_raw)
    sa = sign_of(fmt, a_raw)
    sb = sign_of(fmt, b_raw)
    if isinstance(la, Special) and la.kind == "nar": return fmt.nar
    if isinstance(lb, Special) and lb.kind == "nar": return fmt.nar
    a_zero = isinstance(la, Special) and la.kind == "zero"
    b_zero = isinstance(lb, Special) and lb.kind == "zero"
    if a_zero and b_zero:
        return fmt.pos_zero
    if a_zero:
        return b_raw
    if b_zero:
        return a_raw

    # value_a + value_b = s_a*2^la + s_b*2^lb
    # если sa == sb: |sum| = 2^la + 2^lb; log_sum = max(la,lb) + log2(1 + 2^(min-max))
    # если sa != sb: |sum| = |2^la - 2^lb|; log_sum = max + log2(|1 - 2^(min-max)|)
    if la >= lb:
        big, small, sbig = la, lb, sa
    else:
        big, small, sbig = lb, la, sb
    diff = small - big  # <= 0
    diff_float = float(diff)
    if sa == sb:
        mag = 1.0 + (2.0 ** diff_float)
        rsign = sa
    else:
        mag = abs(1.0 - (2.0 ** diff_float))
        if mag == 0.0:
            return fmt.pos_zero  # exact cancellation
        rsign = sbig
    log_sum = Fraction(big) + Fraction(math.log2(mag)).limit_denominator(1 << fmt.frac_bits)
    return encode_from_log(fmt, rsign, log_sum)


def _selftest():
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    for fname, fmt in FORMATS.items():
        # zero
        check(decode(fmt, fmt.pos_zero) == 0, f"{fname}: pos_zero -> 0")
        # unity: log=0, sign=0 -> value 1 (exact power of 2)
        one = encode_from_log(fmt, 0, Fraction(0))
        check(decode(fmt, one) == 1, f"{fname}: unity value==1 (raw 0x{one:x})")
        # 2.0 = 2^1
        two = encode_from_log(fmt, 0, Fraction(1))
        check(decode(fmt, two) == 2, f"{fname}: 2^1 -> 2")
        # 4.0 = 2^2
        four = encode_from_log(fmt, 0, Fraction(2))
        check(decode(fmt, four) == 4, f"{fname}: 2^2 -> 4")

        # mul is EXACT in log domain: 2^a * 2^b = 2^(a+b)
        # 2 * 4 = 8  (log 1 + log 2 = log 3)
        r = format_mul(fmt, two, four)
        check(decode(fmt, r) == 8, f"{fname}: 2*4=8 (got {decode(fmt, r)})")
        # 1 * 1 = 1
        r = format_mul(fmt, one, one)
        check(decode(fmt, r) == 1, f"{fname}: 1*1=1")

        # add: 1 + 1 = 2  (both unity, exact result is power of 2)
        r = format_add(fmt, one, one)
        check(decode(fmt, r) == 2, f"{fname}: 1+1=2 (got {decode(fmt, r)})")

        # x + 0 == x  (when x is a representable log)
        check(format_add(fmt, two, fmt.pos_zero) == two, f"{fname}: x+0==x")

    if failures:
        print("SELF-TEST: FAIL (%d)" % len(failures))
        for f in failures[:20]:
            print("  " + f)
        return 1
    print("SELF-TEST: PASS (lns: zero/unity/powers-of-2/mul-exact/1+1/x+0)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
