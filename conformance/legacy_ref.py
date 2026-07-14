#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
legacy_ref.py — ЭТАЛОННЫЙ (golden) оракул для legacy форматов с плавающей точкой.
  vax_f, vax_d, vax_g, vax_h        — DEC VAX (base 2, hidden 1, bias 128/1024/16384)
  ibm_hfp32, ibm_hfp64, ibm_hfp128   — IBM hex FP (base 16, no hidden bit, bias 64)
  cray_float                         — Cray-1 (base 2, explicit leading 1, bias 16384)
  pdp11_float                        — PDP-11 F (predecessor of VAX F, bias 128)
  x87_fp80                           — Intel 80-bit extended (explicit integer bit, bias 16383)
  x87_48bit                          — 48-bit x87-style truncated (bias 16383)

Каждый формат со своим encoding-правилом; общие — round-ties-even и точная
Fraction-арифметика. По образцу gf_ref.py.

Согласовано с conformance/ibm_hfp32_decode_conformance_ax7203.py и
conformance/vax_f_decode_conformance_ax7203.py.

Honesty: Trinity conformance team.
"""

from fractions import Fraction
from dataclasses import dataclass


@dataclass(frozen=True)
class LegacyFormat:
    name: str
    width: int
    kind: str               # 'vax' | 'ibm' | 'cray' | 'x87'
    exp_bits: int
    mant_bits: int
    bias: int
    base: int = 2           # 2 or 16
    explicit_int_bit: bool = False   # Cray/x87: leading bit explicit (no hidden)

    @property
    def mask(self): return (1 << self.width) - 1
    @property
    def sign_shift(self): return self.width - 1
    @property
    def exp_max(self): return (1 << self.exp_bits) - 1
    @property
    def mant_max(self): return (1 << self.mant_bits) - 1
    @property
    def mant_shift(self): return 0   # mantissa occupies low bits
    @property
    def pos_zero(self): return 0
    @property
    def neg_zero(self): return 1 << self.sign_shift
    @property
    def quiet_nan(self):
        # legacy formats have no canonical NaN; use a reserved exp/max-mant pattern
        return (self.exp_max << self.mant_bits) | 1


FORMATS = {
    "vax_f":       LegacyFormat("vax_f",       width=32,  kind='vax',  exp_bits=8,  mant_bits=23, bias=128),
    "vax_d":       LegacyFormat("vax_d",       width=64,  kind='vax',  exp_bits=8,  mant_bits=55, bias=128),
    "vax_g":       LegacyFormat("vax_g",       width=64,  kind='vax',  exp_bits=11, mant_bits=52, bias=1024),
    "vax_h":       LegacyFormat("vax_h",       width=128, kind='vax',  exp_bits=15, mant_bits=112, bias=16384),
    "ibm_hfp32":   LegacyFormat("ibm_hfp32",   width=32,  kind='ibm',  exp_bits=7,  mant_bits=24, bias=64, base=16),
    "ibm_hfp64":   LegacyFormat("ibm_hfp64",   width=64,  kind='ibm',  exp_bits=7,  mant_bits=56, bias=64, base=16),
    "ibm_hfp128":  LegacyFormat("ibm_hfp128",  width=128, kind='ibm',  exp_bits=7,  mant_bits=120, bias=64, base=16),
    "cray_float":  LegacyFormat("cray_float",  width=64,  kind='cray', exp_bits=15, mant_bits=48, bias=16384, explicit_int_bit=True),
    "pdp11_float": LegacyFormat("pdp11_float", width=32,  kind='vax',  exp_bits=8,  mant_bits=23, bias=128),
    "x87_fp80":    LegacyFormat("x87_fp80",    width=80,  kind='x87',  exp_bits=15, mant_bits=64, bias=16383, explicit_int_bit=True),
    "x87_48bit":   LegacyFormat("x87_48bit",   width=48,  kind='x87',  exp_bits=15, mant_bits=32, bias=16383, explicit_int_bit=True),
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


def ilog2_base(a: Fraction, base: int) -> int:
    """floor(log_base(a)) для точной положительной Fraction (base 2 or 16)."""
    assert a > 0
    n, d = a.numerator, a.denominator
    e = n.bit_length() - d.bit_length()
    if Fraction(n, d) < pow2(e):
        e -= 1
    while Fraction(n, d) >= pow2(e + 1):
        e += 1
    if base == 2:
        return e
    # base 16: floor(log16(a)) = floor(log2(a) / 4)  (Python // floors toward -inf)
    return e // 4


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


def decode(fmt: LegacyFormat, raw: int):
    raw &= fmt.mask
    if raw == 0:
        return Fraction(0)

    sign = (raw >> fmt.sign_shift) & 1
    exp = (raw >> fmt.mant_bits) & fmt.exp_max
    mant = raw & fmt.mant_max

    if fmt.kind == 'ibm':
        if exp == 0:
            return Fraction(0)
        value = Fraction(mant, 1 << fmt.mant_bits) * (Fraction(fmt.base) ** (exp - fmt.bias))
        return -value if sign else value

    if fmt.kind == 'vax':
        if exp == 0:
            return Fraction(0)        # VAX reserves exp=0 for zero
        value = (1 + Fraction(mant, 1 << fmt.mant_bits)) * pow2(exp - fmt.bias)
        return -value if sign else value

    if fmt.kind in ('cray', 'x87'):
        # explicit integer bit at position (mant_bits-1): value = mant/2^(M-1) * 2^(e-bias)
        if fmt.kind == 'x87' and exp == 0:
            if mant == 0:
                return Fraction(0)
            value = Fraction(mant, 1 << (fmt.mant_bits - 1)) * pow2(1 - fmt.bias)
            return -value if sign else value
        value = Fraction(mant, 1 << (fmt.mant_bits - 1)) * pow2(exp - fmt.bias)
        return -value if sign else value

    raise ValueError(fmt.kind)


def _sat_raw(fmt: LegacyFormat, sign: int) -> int:
    """Saturate to max-magnitude finite (legacy formats have no Inf)."""
    sat = (fmt.exp_max << fmt.mant_bits) | fmt.mant_max
    return ((1 << fmt.sign_shift) | sat) if sign else sat


def encode(fmt: LegacyFormat, value):
    if isinstance(value, Special):
        return fmt.quiet_nan

    v = Fraction(value)
    if v == 0:
        return fmt.pos_zero

    sign = 1 if v < 0 else 0
    a = -v if v < 0 else v

    if fmt.kind == 'ibm':
        # value = (F/2^M) * 16^(E-bias), F normalized in [2^(M-4), 2^M) when E >= 1.
        # IBM allows UNNORMALIZED encodings: at the minimum exponent E=1, a sub-normal
        # region (leading-zero hex digits) covers [0, 16^(1-bias)) gradually.
        M = fmt.mant_bits
        g = ilog2_base(a, 16)                 # 16^g <= a < 16^(g+1)
        E = g + 1 + fmt.bias                   # biased; normalized fraction in [1/16,1)
        sub = E < 1
        if sub:
            E = 1                              # clamp to minimum exponent (gradual underflow)
        F_real = a / (Fraction(fmt.base) ** (E - fmt.bias)) * (1 << M)
        F, _ = _round_half_even(F_real)
        if F == 0:
            return fmt.pos_zero                # underflow
        if F >= (1 << M):
            if sub:
                F = (1 << M) - 1               # clamp at max sub-normal fraction
            else:                              # rounded up to 1.0 -> renormalize
                F = 1 << (M - 4)
                E += 1
        if E > fmt.exp_max:
            return _sat_raw(fmt, sign)
        return (sign << fmt.sign_shift) | (E << M) | (F & fmt.mant_max)

    if fmt.kind == 'vax':
        M = fmt.mant_bits
        E2 = ilog2_base(a, 2)
        frac = a / pow2(E2) - 1                # [0,1)
        F, carry = _round_half_even(frac * (1 << M), cap=(1 << M))
        e = E2 + fmt.bias
        if carry:
            F = 0
            e += 1
        if e <= 0:
            return fmt.pos_zero                # VAX flushes denormals to zero
        if e > fmt.exp_max:
            return _sat_raw(fmt, sign)
        return (sign << fmt.sign_shift) | (e << M) | (F & fmt.mant_max)

    if fmt.kind in ('cray', 'x87'):
        M = fmt.mant_bits
        E2 = ilog2_base(a, 2)
        e = E2 + fmt.bias
        # significand with explicit integer bit: sig = a/2^E2 * 2^(M-1), in [2^(M-1), 2^M) normal
        if fmt.kind == 'x87' and e <= 0:
            # 8087 gradual underflow at exp=0 (integer bit 0): sig scaled by 2^(bias-1)
            if e < 1 - fmt.bias - (M - 1):
                return fmt.pos_zero
            sigd, _ = _round_half_even(a * (1 << (M - 1)) * pow2(fmt.bias - 1))
            if sigd == 0:
                return fmt.pos_zero
            return (sign << fmt.sign_shift) | (sigd & fmt.mant_max)
        if e < 1:
            # Cray: no exp=0 denormals, but allows UNNORMALIZED (integer bit 0) at exp=1
            e = 1
            sub = True
        else:
            sub = False
        sig_real = (a / pow2(e - fmt.bias)) * (1 << (M - 1))
        sig, carry = _round_half_even(sig_real, cap=(1 << M))
        if sig == 0:
            return fmt.pos_zero
        if carry:
            if sub:
                sig = (1 << M) - 1
            else:
                sig = 1 << (M - 1)
                e += 1
        if e > fmt.exp_max:
            return _sat_raw(fmt, sign)
        return (sign << fmt.sign_shift) | (e << M) | (sig & fmt.mant_max)

    raise ValueError(fmt.kind)


def format_add(fmt: LegacyFormat, a_raw: int, b_raw: int) -> int:
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    if isinstance(a, Special) or isinstance(b, Special):
        return fmt.quiet_nan
    sa = (a_raw >> fmt.sign_shift) & 1
    sb = (b_raw >> fmt.sign_shift) & 1
    if a == 0 and b == 0:
        return fmt.neg_zero if (sa == 1 and sb == 1) else fmt.pos_zero
    return encode(fmt, a + b)


def format_mul(fmt: LegacyFormat, a_raw: int, b_raw: int) -> int:
    a = decode(fmt, a_raw)
    b = decode(fmt, b_raw)
    if isinstance(a, Special) or isinstance(b, Special):
        return fmt.quiet_nan
    sa = (a_raw >> fmt.sign_shift) & 1
    sb = (b_raw >> fmt.sign_shift) & 1
    rsign = sa ^ sb
    if a == 0 or b == 0:
        return fmt.neg_zero if rsign else fmt.pos_zero
    return encode(fmt, a * b)


def _selftest():
    import random
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    # IBM HFP32 known vectors
    ibm32 = FORMATS["ibm_hfp32"]
    check(decode(ibm32, 0x41100000) == 1, "ibm_hfp32: 0x41100000 -> +1")
    check(decode(ibm32, 0xC1100000) == -1, "ibm_hfp32: 0xC1100000 -> -1")
    check(decode(ibm32, 0x41200000) == 2, "ibm_hfp32: 0x41200000 -> +2")

    for fname, fmt in FORMATS.items():
        check(decode(fmt, 0) == 0, f"{fname}: +0")
        check(encode(fmt, 0) == 0, f"{fname}: encode 0")
        one = encode(fmt, Fraction(1))
        check(decode(fmt, one) == 1, f"{fname}: unity (0x{one:x})")
        r = format_add(fmt, one, one)
        check(decode(fmt, r) == 2, f"{fname}: 1+1=2 (got {decode(fmt, r)})")
        check(format_add(fmt, 0, 0) == 0, f"{fname}: 0+0=0")

        if fmt.width <= 16:
            codes = range(0, 1 << fmt.width)
        else:
            rng = random.Random(0x1E6A + fmt.width)
            codes = [rng.randrange(1 << fmt.width) for _ in range(20000)]
        for raw in codes:
            v = decode(fmt, raw)
            if isinstance(v, Special) or v == 0:
                continue
            # x + 0 preserves VALUE (bit-exact for uniquely-encoded formats;
            # IBM/VAX may normalize to a canonical pattern — value must match).
            r0 = format_add(fmt, raw, 0)
            check(decode(fmt, r0) == v, f"{fname}: x+0 value 0x{raw:x}")

    if failures:
        print("SELF-TEST: FAIL (%d)" % len(failures))
        for f in failures[:20]:
            print("  " + f)
        return 1
    print("SELF-TEST: PASS (legacy: known-ibm/zero/unity/1+1/x+0)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
