#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
decimal_ref.py — ЭТАЛОННЫЙ (golden) оракул для IEEE 754 decimal BID-семейства.
  decimal32, decimal64, decimal128 (Binary Integer Decimal).

Кодировка BID (IEEE 754-2008): sign + combination + coefficient C (binary int).
  value = (-1)^s * C * 10^(E - bias)
  Case A (C < 2^M_small): combination top2 != 11; E = exp field, C = lower bits.
  Case B (C в [2^M_small, 2^M_big)): combination top2 == 11, top4 != 1111;
           C = implicit "100" MSBs | lower bits.
  Specials: top4 == 11110 -> Inf ; top4 == 11111 -> NaN.

Коэффициент и порядок — точные целые; само значение 10^(E-bias) — целая степень 10,
поэтому value = C * 10^(E-bias) представимо ТОЧНО как Fraction (целое/целое).
Round-ties-even при encode (выбор ближайшего C). По образцу gf_ref.py.

Согласовано с conformance/decimal64_decode_conformance_ax7203.py (BID decode).

Honesty: Trinity conformance team.
"""

from fractions import Fraction
from dataclasses import dataclass


@dataclass(frozen=True)
class DecimalFormat:
    name: str
    width: int
    exp_bits: int        # width of biased exponent field
    coeff_bits_small: int  # M_small: coefficient bits in case A (C < 2^M_small)
    coeff_bits_big: int    # M_big:   coefficient bits in case B
    bias: int            # E_unbiased = E_field - bias
    max_coeff: int       # maximum representable coefficient (decimal digit count)

    @property
    def mask(self): return (1 << self.width) - 1
    @property
    def sign_shift(self): return self.width - 1
    @property
    def pos_zero(self): return 0
    @property
    def neg_zero(self): return 1 << self.sign_shift
    @property
    def exp_max(self): return (1 << self.exp_bits) - 1
    @property
    def pos_inf(self):
        # bits [width-2 : width-6] = 11110  (5-bit special tag below sign)
        return (0b11110 << (self.width - 6)) & self.mask
    @property
    def neg_inf(self):
        return self.pos_inf | (1 << self.sign_shift)
    @property
    def quiet_nan(self):
        # bits [width-2 : width-6] = 11111
        return (0b11111 << (self.width - 6)) & self.mask


# IEEE 754-2008 BID parameters.
FORMATS = {
    "decimal32":  DecimalFormat("decimal32",  width=32,  exp_bits=8,
                                coeff_bits_small=23, coeff_bits_big=24, bias=101,
                                max_coeff=9999999),        # 7 digits
    "decimal64":  DecimalFormat("decimal64",  width=64,  exp_bits=10,
                                coeff_bits_small=53, coeff_bits_big=54, bias=398,
                                max_coeff=9999999999999999),  # 16 digits
    "decimal128": DecimalFormat("decimal128", width=128, exp_bits=14,
                                coeff_bits_small=113, coeff_bits_big=114, bias=6176,
                                max_coeff=10**34 - 1),         # 34 digits
}


class Special:
    def __init__(self, kind, sign=0):
        self.kind = kind
        self.sign = sign

    def __repr__(self):
        if self.kind == "nan":
            return "NaN"
        return ("-" if self.sign else "+") + "Inf"


def pow10(e: int):
    return 10 ** e if e >= 0 else Fraction(1, 10 ** (-e))


def _bid_decode(fmt: DecimalFormat, code: int):
    """Return ('finite', sign, C, E_field) | ('inf', sign) | ('nan', sign)."""
    code &= fmt.mask
    sign = (code >> fmt.sign_shift) & 1
    cf_hi = (code >> (fmt.sign_shift - 2)) & 0x3          # top 2 bits of combination
    if cf_hi != 0b11:                                      # case A
        E = (code >> fmt.coeff_bits_small) & fmt.exp_max
        C = code & ((1 << fmt.coeff_bits_small) - 1)
        return ("finite", sign, C, E)
    cf_top4 = (code >> (fmt.sign_shift - 4)) & 0xF
    if cf_top4 == 0b1111:
        is_nan = (code >> (fmt.sign_shift - 5)) & 1
        return ("nan", sign) if is_nan else ("inf", sign)
    # case B: implicit "100" prefix on coefficient
    E = (code >> fmt.coeff_bits_big - 3) & fmt.exp_max     # exp field right above lower coeff bits
    C = (0b100 << (fmt.coeff_bits_big - 3)) | (code & ((1 << (fmt.coeff_bits_big - 3)) - 1))
    return ("finite", sign, C, E)


def _bid_encode_fields(fmt: DecimalFormat, sign: int, C: int, E: int) -> int:
    """Pack finite (sign, C, E_field) -> BID code (case A or B)."""
    small_cap = 1 << fmt.coeff_bits_small
    if C < small_cap:
        return ((sign << fmt.sign_shift)
                | ((E & fmt.exp_max) << fmt.coeff_bits_small)
                | C) & fmt.mask
    # case B: C must fit in coeff_bits_big with implicit 100 prefix
    assert (C >> (fmt.coeff_bits_big - 3)) == 0b100, "case B coeff prefix"
    lower_bits = fmt.coeff_bits_big - 3
    return ((sign << fmt.sign_shift)
            | (0b11 << (fmt.sign_shift - 2))
            | ((E & fmt.exp_max) << lower_bits)
            | (C & ((1 << lower_bits) - 1))) & fmt.mask


def decode(fmt: DecimalFormat, raw: int):
    kind = _bid_decode(fmt, raw)
    if kind[0] == "inf":
        return Special("inf", kind[1])
    if kind[0] == "nan":
        return Special("nan", kind[1])
    _, sign, C, E = kind
    if C == 0:
        return Fraction(0)
    de = E - fmt.bias
    val = Fraction(C) * pow10(de)
    return -val if sign else val


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


def encode(fmt: DecimalFormat, value):
    if isinstance(value, Special):
        if value.kind == "nan":
            return fmt.quiet_nan
        return fmt.neg_inf if value.sign else fmt.pos_inf

    v = Fraction(value)
    if v == 0:
        return fmt.pos_zero

    sign = 1 if v < 0 else 0
    a = -v if v < 0 else v          # exact positive Fraction

    # value = C * 10^(E - bias), 0 < C <= max_coeff (integer), E in [0, exp_max].
    # Factor a into integer coeff * power of 10. Extract powers of 2 and 5.
    num = a.numerator
    den = a.denominator
    # remove powers of 10 (2*5) from denominator and numerator to get C as integer
    e10 = 0
    # cancel common 2/5 between num and den first (Fraction already reduced, but den
    # may still contain 2s and 5s representing the negative power of 10).
    # decompose denominator into 2^a * 5^b * rest
    def split(n, base):
        k = 0
        while n > 1 and n % base == 0:
            n //= base
            k += 1
        return k, n
    n2, rest = split(den, 2)
    n5, rest = split(rest, 5)
    if rest != 1:
        # denominator has primes other than 2,5 -> value not exactly representable
        # as C * 10^e. Round: choose E to maximize coefficient precision.
        return _encode_round(fmt, sign, a)
    den10 = max(n2, n5)
    # bring to common power of 10: denominator currently 2^n2 * 5^n5, target 10^den10 = 2^den10 * 5^den10
    C = num
    if n2 < den10:
        C *= 2 ** (den10 - n2)    # compensate missing factors of 2 in denominator
    if n5 < den10:
        C *= 5 ** (den10 - n5)    # compensate missing factors of 5 in denominator
    # a = C * 10^(-den10). Pull factors of 10 out of C (minimize C, maximize exponent):
    # C = 10*C'  =>  a = C' * 10^(1-den10), so den10 decreases by 1.
    while C % 10 == 0 and C > 0:
        C //= 10
        den10 -= 1
    E = fmt.bias - den10
    # now value = C * 10^(E - bias). Fold exponent into C while E exceeds range.
    while E > fmt.exp_max and C * 10 <= fmt.max_coeff:
        C *= 10
        E -= 1
    if E < 0 or E > fmt.exp_max or C > fmt.max_coeff or C == 0:
        return _encode_round(fmt, sign, a)
    return _bid_encode_fields(fmt, sign, C, E)


def _encode_round(fmt: DecimalFormat, sign: int, a: Fraction) -> int:
    """General RNE encode: find (C, E) with 0<C<=max_coeff, 0<=E<=exp_max minimizing error."""
    best = None
    best_err = None
    # scan plausible exponent window around log10(a)
    import math
    try:
        eapprox = int(math.floor(math.log10(float(a)))) + fmt.bias
    except (OverflowError, ValueError):
        eapprox = fmt.bias
    for E in range(max(0, eapprox - 3), min(fmt.exp_max, eapprox + 3) + 1):
        scale = pow10(E - fmt.bias)        # 10^(E-bias)
        C_real = a / scale                 # exact Fraction
        C, _ = _round_half_even(C_real)
        if C == 0:
            continue
        if C > fmt.max_coeff:
            continue
        cand = Fraction(C) * scale
        err = abs(cand - a)
        if best_err is None or err < best_err or (err == best_err and C < best[0]):
            best_err = err
            best = (C, E)
    if best is None:
        # overflow or underflow
        if a > (fmt.max_coeff * pow10(fmt.exp_max - fmt.bias)):
            return fmt.neg_inf if sign else fmt.pos_inf
        return (sign << fmt.sign_shift) if fmt.name != "decimal128" else (sign << fmt.sign_shift)
    C, E = best
    return _bid_encode_fields(fmt, sign, C, E)


def format_add(fmt: DecimalFormat, a_raw: int, b_raw: int) -> int:
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    if isinstance(a, Special) and a.kind == "nan": return fmt.quiet_nan
    if isinstance(b, Special) and b.kind == "nan": return fmt.quiet_nan
    if isinstance(a, Special) and a.kind == "inf":
        if isinstance(b, Special) and b.kind == "inf" and b.sign != a.sign:
            return fmt.quiet_nan
        return fmt.neg_inf if a.sign else fmt.pos_inf
    if isinstance(b, Special) and b.kind == "inf":
        return fmt.neg_inf if b.sign else fmt.pos_inf
    sa = (a_raw >> fmt.sign_shift) & 1
    sb = (b_raw >> fmt.sign_shift) & 1
    if a == 0 and b == 0:
        return fmt.neg_zero if (sa == 1 and sb == 1) else fmt.pos_zero
    return encode(fmt, a + b)


def format_mul(fmt: DecimalFormat, a_raw: int, b_raw: int) -> int:
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    if isinstance(a, Special) and a.kind == "nan": return fmt.quiet_nan
    if isinstance(b, Special) and b.kind == "nan": return fmt.quiet_nan
    a_inf = isinstance(a, Special) and a.kind == "inf"
    b_inf = isinstance(b, Special) and b.kind == "inf"
    sa = (a_raw >> fmt.sign_shift) & 1
    sb = (b_raw >> fmt.sign_shift) & 1
    rsign = sa ^ sb
    if a_inf or b_inf:
        if a == 0 or b == 0:
            return fmt.quiet_nan
        return fmt.neg_inf if rsign else fmt.pos_inf
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

        # unity: C=1, E=bias
        one = _bid_encode_fields(fmt, 0, 1, fmt.bias)
        check(decode(fmt, one) == 1, f"{fname}: unity (0x{one:x})")
        check(encode(fmt, Fraction(1)) == one, f"{fname}: encode 1")

        # 1 + 1 = 2
        r = format_add(fmt, one, one)
        check(decode(fmt, r) == 2, f"{fname}: 1+1=2 (got {decode(fmt, r)})")
        check(format_add(fmt, 0, 0) == 0, f"{fname}: 0+0=0")

        # 2*C + 0 == identity for representible values
        two = format_add(fmt, one, one)
        check(format_add(fmt, two, 0) == two, f"{fname}: x+0==x")

        # Inf / NaN
        check(isinstance(decode(fmt, fmt.pos_inf), Special), f"{fname}: +Inf")
        check(isinstance(decode(fmt, fmt.quiet_nan), Special), f"{fname}: NaN")

        # decimal arithmetic exactness: 0.5 + 0.5 = 1
        half = encode(fmt, Fraction(1, 2))
        check(decode(fmt, format_add(fmt, half, half)) == 1, f"{fname}: 0.5+0.5=1")

    if failures:
        print("SELF-TEST: FAIL (%d)" % len(failures))
        for f in failures[:20]:
            print("  " + f)
        return 1
    print("SELF-TEST: PASS (decimal BID: zero/unity/inf/nan/1+1/0.5+0.5/x+0)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
