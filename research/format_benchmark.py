#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
format_benchmark.py — head-to-head accuracy comparison of ~16-bit number formats.

Compares GoldenFloat (GF16/GF12), Posit(16,1), MXFP8 (E4M3), BF16, FP16, and
Takum16 on four vector suites against an exact-arithmetic (Fraction) oracle.

Output:
  - formatted table to stdout
  - CSV at research/format_accuracy_results.csv

Author: Trinity catalog benchmark (Agent N + Agent S), 2026-07-14.
Honesty: this is an *accuracy* benchmark only. LUT cost is reported separately
in lut_comparison.md. No superiority claim is implied by any single cell.
Formats are evaluated at their native width; cross-format comparison is
illustrative, not a controlled experiment (formats differ in dynamic range).
"""

import csv
import math
import os
import random
import sys
from fractions import Fraction

# Reuse the canonical GoldenFloat oracle from conformance/gf_ref.py so GF numbers
# match the silicon-conformance reference exactly.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, os.path.join(REPO_ROOT, "conformance"))
import gf_ref  # noqa: E402  (canonical GF oracle, Fraction-based, RNE)


# =====================================================================
# Format interface — every format implements encode_value/decode_value
# returning a Python Fraction (or None for non-finite), plus a short
# description of its field layout.
# =====================================================================

class Format:
    """Base class. Subclasses implement encode/decode against a Fraction."""
    name = "?"
    layout = "?"
    total_bits = 0

    def encode(self, x):
        """x: Fraction (finite). Return raw integer code."""
        raise NotImplementedError

    def decode(self, raw):
        """raw: int. Return Fraction (finite) or None for Inf/NaN/NaR."""
        raise NotImplementedError

    def quantize(self, x):
        """Round-trip a Fraction through this format. Returns Fraction or None."""
        if x == 0:
            return Fraction(0)
        raw = self.encode(x)
        return self.decode(raw)


# -------------------- GoldenFloat (via canonical gf_ref oracle) --------------------

class _GFAdapter(Format):
    """Adapter that wraps gf_ref.GFFormat so all GF widths share one path."""

    def __init__(self, key, label, layout):
        self.fmt = gf_ref.FORMATS[key]
        self.name = label
        self.layout = layout
        self.total_bits = self.fmt.width

    def encode(self, x):
        # gf_ref.encode handles finite Fractions; specials are out of scope here.
        if x == 0:
            return self.fmt.pos_zero
        return gf_ref.encode(self.fmt, x)

    def decode(self, raw):
        v = gf_ref.decode(self.fmt, raw)
        if isinstance(v, gf_ref.Special):
            return None
        return v


gf16 = _GFAdapter("gf16", "GF16", "[1|6|9] E=6 M=9 bias=31 (+Inf/NaN)")
gf12 = _GFAdapter("gf12", "GF12", "[1|4|7] E=4 M=7 bias=7 (no Inf)")


# -------------------- Posit(16,1) — minimal faithful encode/decode --------------------
# Reference: Gustafson, "Beating Floating Point at its Own Game: Posit Arithmetic"
# (2017). 1 sign + variable regime + 1 exp bit + fraction. es=1.

class Posit16_1(Format):
    name = "Posit16,1"
    layout = "[1|regime|1 exp|frac] es=1"
    total_bits = 16
    N = 16
    ES = 1
    USEED = 2 ** (2 ** ES)  # 16

    def decode(self, raw):
        raw &= (1 << self.N) - 1
        if raw == 0:
            return Fraction(0)
        if raw == (1 << (self.N - 1)):  # NaR
            return None
        sign = (raw >> (self.N - 1)) & 1
        if sign:
            raw = ((~raw + 1) & ((1 << self.N) - 1))  # two's complement on N bits
        # regime: count run bits after sign
        bits = [(raw >> i) & 1 for i in range(self.N - 2, -1, -1)]
        # bits[0] is the MSB of the regime field
        first = bits[0]
        run = 0
        idx = 0
        while idx < len(bits) and bits[idx] == first:
            run += 1
            idx += 1
        # Posit regime: run of `run` identical bits + terminator.
        #   first==1: k = run - 1     ([1,0]→k=0, [1,1,0]→k=1, ...)
        #   first==0: k = -run        ([0,1]→k=-1, [0,0,1]→k=-2, ...)
        k = (run - 1) if first == 1 else (-run)
        # Skip the terminator bit (the first opposite-valued bit after the run),
        # if one exists within the field.
        if idx < len(bits):
            idx += 1
        # exponent (ES bits) after regime
        exp_bits = []
        for _ in range(self.ES):
            if idx < len(bits):
                exp_bits.append(bits[idx])
                idx += 1
            else:
                exp_bits.append(0)
        e = 0
        for b in exp_bits:
            e = (e << 1) | b
        # remaining bits = fraction
        frac_bits = bits[idx:]
        f = Fraction(0)
        for i, b in enumerate(frac_bits, start=1):
            if b:
                f += Fraction(1, 1 << i)
        exponent = k * (1 << self.ES) + e
        val = (1 + f) * Fraction(2) ** exponent
        return -val if sign else val

    def encode(self, x):
        # Faithful posit(16,1) rounding via long-Fraction arithmetic.
        sign = 1 if x < 0 else 0
        a = -x if x < 0 else x
        if a == 0:
            return 0
        # Find k such that USEED^k <= a < USEED^(k+1)  (i.e. 2^(4k) <= a < 2^(4k+4))
        e_real = _floor_log2(a)
        k = e_real >> self.ES  # floor division by 2 (es=1): useed=2^4
        # Build the scaled fraction: a = useed^k * 2^e * (1+f), with e in {0,1}
        scaled = a * Fraction(2) ** (-k * (1 << self.ES))
        # scaled in [1, 16). pick e in {0,1} so scaled/2^e in [1,2).
        e = 0
        if scaled >= 4:
            e = 1
            scaled /= 4
        elif scaled >= 2:
            e = 1
            scaled /= 2
        # now scaled in [1, 2): mantissa fraction = scaled - 1
        frac = scaled - 1
        # regime field length:
        #   k>=0: (k+1) ones + a zero = k+2 bits
        #   k<0:  (-k) zeros + a one = -k+1 bits
        regime_len = (k + 2) if k >= 0 else (-k + 1)
        avail_frac_bits = self.N - 1 - regime_len - self.ES
        if avail_frac_bits <= 0:
            # Not enough room for any fraction bit; round at the regime/exp boundary.
            if frac >= Fraction(1, 2):
                if e == 1:
                    e = 0
                    k += 1
                else:
                    e = 1
            return self._pack(sign, k, e, 0)
        # round frac to avail_frac_bits (round-to-nearest-even)
        scale = 1 << avail_frac_bits
        scaled_frac = frac * scale
        fl = scaled_frac.numerator // scaled_frac.denominator
        rem = scaled_frac - fl
        half = Fraction(1, 2)
        if rem > half or (rem == half and (fl % 2 == 1)):
            fl += 1
        if fl >= scale:  # carry into integer part
            fl = 0
            if e == 1:
                e = 0
                k += 1
            else:
                e = 1
            # regime_len may have changed if k changed sign/magnitude — recompute
            regime_len = (k + 2) if k >= 0 else (-k + 1)
            avail_frac_bits = self.N - 1 - regime_len - self.ES
            if avail_frac_bits < 0:
                avail_frac_bits = 0
        return self._pack(sign, k, e, fl, avail_frac_bits)

    def _pack(self, sign, k, e, frac_val, frac_bits=None):
        n = self.N
        # Build the n-bit unsigned-magnitude posit (sign bit added last via 2's compl)
        bits = []
        # regime: k>=0 → (k+1) ones + zero; k<0 → (-k) zeros + one
        if k >= 0:
            regime = [1] * (k + 1) + [0]
        else:
            regime = [0] * (-k) + [1]
        bits.extend(regime)
        # exponent (ES bits, MSB first)
        for i in range(self.ES - 1, -1, -1):
            bits.append((e >> i) & 1)
        # fraction
        if frac_bits is None:
            frac_bits = max(0, n - 1 - len(regime) - self.ES)
        for i in range(frac_bits - 1, -1, -1):
            bits.append((frac_val >> i) & 1)
        # truncate / pad to N-1 bits (sign is separate)
        mag_bits = bits[: n - 1]
        while len(mag_bits) < n - 1:
            mag_bits.append(0)
        raw = 0
        for b in mag_bits:
            raw = (raw << 1) | b
        if sign:
            # two's complement on N bits
            raw = ((~raw) + 1) & ((1 << (n - 1)) - 1)
            raw |= (1 << (n - 1))
            raw &= (1 << n) - 1
        return raw


def _pow2(e: int) -> Fraction:
    if e >= 0:
        return Fraction(1 << e, 1)
    return Fraction(1, 1 << (-e))


def _floor_log2(a: Fraction) -> int:
    n, d = a.numerator, a.denominator
    e = n.bit_length() - d.bit_length()
    if Fraction(n, d) < _pow2(e):
        e -= 1
    while Fraction(n, d) >= _pow2(e + 1):
        e += 1
    return e


posit16 = Posit16_1()


# -------------------- MXFP8 (E4M3) — OCP FP8 --------------------
# Micikevicius et al., "FP8 Formats for Deep Learning" (arXiv:2209.05433).
# E4M3: bias=7; max-exponent 0b1111 with mant=0b111 is NaN; 0b1111 mant!=111 is finite max.

class MXFP8(Format):
    name = "MXFP8 (E4M3)"
    layout = "[1|4|3] bias=7 (no Inf; max finite)"
    total_bits = 8
    E_BITS = 4
    M_BITS = 3
    BIAS = 7

    def decode(self, raw):
        raw &= 0xFF
        sign = (raw >> 7) & 1
        exp = (raw >> 3) & 0xF
        mant = raw & 0x7
        if exp == 0b1111 and mant == 0b111:
            return None  # NaN
        if exp == 0:
            if mant == 0:
                return Fraction(0)
            val = Fraction(mant, 8) * Fraction(2) ** (1 - self.BIAS)
        else:
            # E4M3 special: exp=1111 (with mant!=111) is FINITE (the largest finite),
            # unlike IEEE which reserves it for Inf. Implicit bit = 1.
            val = (1 + Fraction(mant, 8)) * Fraction(2) ** (exp - self.BIAS)
        return -val if sign else val

    def encode(self, x):
        sign = 1 if x < 0 else 0
        a = -x if x < 0 else x
        if a == 0:
            return 0
        E = _floor_log2(a)
        exp_field = E + self.BIAS
        max_exp = 0b1111  # E4M3: 1111 is finite (unless mant=111 → NaN)
        if exp_field >= max_exp:
            # overflow: saturate to largest finite value (exp=1111, mant=110)
            exp_field = max_exp
            mant = 0b110
            return (sign << 7) | (exp_field << 3) | mant
        if exp_field < 1:
            # subnormal: scale by 2^(1-BIAS) = 2^-6
            scale = Fraction(2) ** (1 - self.BIAS)
            m_real = a / scale * (1 << self.M_BITS)
            fl = m_real.numerator // m_real.denominator
            rem = m_real - fl
            half = Fraction(1, 2)
            if rem > half or (rem == half and (fl % 2 == 1)):
                fl += 1
            if fl == 0:
                return (sign << 7)
            if fl > (1 << self.M_BITS) - 1:
                # promoted to smallest normal
                return (sign << 7) | (1 << 3)
            return (sign << 7) | (fl & 0x7)
        # normal
        frac = a / (Fraction(2) ** E) - 1
        scaled = frac * (1 << self.M_BITS)
        fl = scaled.numerator // scaled.denominator
        rem = scaled - fl
        half = Fraction(1, 2)
        if rem > half or (rem == half and (fl % 2 == 1)):
            fl += 1
        if fl >= (1 << self.M_BITS):
            fl = 0
            exp_field += 1
            if exp_field >= max_exp:
                exp_field = max_exp
                fl = 0b110  # saturate
        return (sign << 7) | ((exp_field & 0xF) << 3) | (fl & 0x7)


mxfp8 = MXFP8()


# -------------------- BF16 (bfloat16: 1|8|7) --------------------

class BF16(Format):
    name = "BF16"
    layout = "[1|8|7] bias=127 (IEEE-style)"
    total_bits = 16
    E_BITS = 8
    M_BITS = 7
    BIAS = 127

    def decode(self, raw):
        raw &= 0xFFFF
        sign = (raw >> 15) & 1
        exp = (raw >> 7) & 0xFF
        mant = raw & 0x7F
        if exp == 0xFF:
            return None  # Inf/NaN
        if exp == 0:
            if mant == 0:
                return Fraction(0)
            val = Fraction(mant, 1 << self.M_BITS) * Fraction(2) ** (1 - self.BIAS)
        else:
            val = (1 + Fraction(mant, 1 << self.M_BITS)) * Fraction(2) ** (exp - self.BIAS)
        return -val if sign else val

    def encode(self, x):
        sign = 1 if x < 0 else 0
        a = -x if x < 0 else x
        if a == 0:
            return 0
        E = _floor_log2(a)
        exp_field = E + self.BIAS
        if exp_field >= 0xFE:
            # overflow → Inf (BF16 reserves exp=0xFF for Inf/NaN)
            return (sign << 15) | (0xFF << 7)
        if exp_field < 1:
            scale = Fraction(2) ** (1 - self.BIAS)
            m_real = a / scale * (1 << self.M_BITS)
            fl = m_real.numerator // m_real.denominator
            rem = m_real - fl
            half = Fraction(1, 2)
            if rem > half or (rem == half and (fl % 2 == 1)):
                fl += 1
            if fl == 0:
                return (sign << 15)
            if fl > (1 << self.M_BITS) - 1:
                return (sign << 15) | (1 << 7)
            return (sign << 15) | (fl & 0x7F)
        frac = a / (Fraction(2) ** E) - 1
        scaled = frac * (1 << self.M_BITS)
        fl = scaled.numerator // scaled.denominator
        rem = scaled - fl
        half = Fraction(1, 2)
        if rem > half or (rem == half and (fl % 2 == 1)):
            fl += 1
        if fl >= (1 << self.M_BITS):
            fl = 0
            exp_field += 1
            if exp_field >= 0xFE:
                return (sign << 15) | (0xFF << 7)
        return (sign << 15) | ((exp_field & 0xFF) << 7) | (fl & 0x7F)


bf16 = BF16()


# -------------------- FP16 (IEEE-754 binary16: 1|5|10) --------------------

class FP16(Format):
    name = "FP16"
    layout = "[1|5|10] bias=15 (IEEE-754)"
    total_bits = 16
    E_BITS = 5
    M_BITS = 10
    BIAS = 15

    def decode(self, raw):
        raw &= 0xFFFF
        sign = (raw >> 15) & 1
        exp = (raw >> 10) & 0x1F
        mant = raw & 0x3FF
        if exp == 0x1F:
            return None
        if exp == 0:
            if mant == 0:
                return Fraction(0)
            val = Fraction(mant, 1 << self.M_BITS) * Fraction(2) ** (1 - self.BIAS)
        else:
            val = (1 + Fraction(mant, 1 << self.M_BITS)) * Fraction(2) ** (exp - self.BIAS)
        return -val if sign else val

    def encode(self, x):
        sign = 1 if x < 0 else 0
        a = -x if x < 0 else x
        if a == 0:
            return 0
        E = _floor_log2(a)
        exp_field = E + self.BIAS
        if exp_field >= 0x1E:
            return (sign << 15) | (0x1F << 10)
        if exp_field < 1:
            scale = Fraction(2) ** (1 - self.BIAS)
            m_real = a / scale * (1 << self.M_BITS)
            fl = m_real.numerator // m_real.denominator
            rem = m_real - fl
            half = Fraction(1, 2)
            if rem > half or (rem == half and (fl % 2 == 1)):
                fl += 1
            if fl == 0:
                return (sign << 15)
            if fl > (1 << self.M_BITS) - 1:
                return (sign << 15) | (1 << 10)
            return (sign << 15) | (fl & 0x3FF)
        frac = a / (Fraction(2) ** E) - 1
        scaled = frac * (1 << self.M_BITS)
        fl = scaled.numerator // scaled.denominator
        rem = scaled - fl
        half = Fraction(1, 2)
        if rem > half or (rem == half and (fl % 2 == 1)):
            fl += 1
        if fl >= (1 << self.M_BITS):
            fl = 0
            exp_field += 1
            if exp_field >= 0x1E:
                return (sign << 15) | (0x1F << 10)
        return (sign << 15) | ((exp_field & 0x1F) << 10) | (fl & 0x3FF)


fp16 = FP16()


# -------------------- Takum16 (Hunhold 2024, arXiv:2404.18603) --------------------
# Mirrors the t27-verified second witness used by conformance/takum16_decode_*.
# value = (-1)^S * exp(ell/2), ell reconstructed from S/D/regime/characteristic/mantissa.

_C_BIAS_T16 = [-255, -127, -63, -31, -15, -7, -3, -1,
               0, 1, 3, 7, 15, 31, 63, 127]


class Takum16(Format):
    name = "Takum16"
    layout = "[S|D|R(3)|characteristic|mantissa] logarithmic"
    total_bits = 16
    N = 16

    # Precompute the full 65536-entry decode table once. Takum16 has a small
    # code space, so a one-shot build + bisect for encode is exact and fast.
    _TABLE = None  # lazy: list of (raw, Fraction-value-or-None)

    @staticmethod
    def _decode_raw(raw):
        """Pure (instance-free) takum16 decode, mirrors the t27 golden witness."""
        raw &= 0xFFFF
        if raw == 0:
            return Fraction(0)
        if raw == (1 << (16 - 1)):  # NaR
            return None
        S = (raw >> 15) & 1
        D = (raw >> 14) & 1
        R_uint = (raw >> 11) & 7
        c_bias = _C_BIAS_T16[(D << 3) | R_uint]
        r_eff = (7 - R_uint) if D == 0 else R_uint
        p = 16 - r_eff - 5
        if p < 0:
            p = 0
        lower = raw & ((1 << (r_eff + p)) - 1)
        M_uint = (lower & ((1 << p) - 1)) if p > 0 else 0
        C_uint = ((lower >> p) & ((1 << r_eff) - 1)) if r_eff > 0 else 0
        c = c_bias + C_uint
        m = Fraction(M_uint, 1 << p) if p > 0 else Fraction(0)
        ell = (1 - 2 * S) * (Fraction(c) + m)
        return _exp_ell_half_to_fraction(ell, S)

    @classmethod
    def _build_table(cls):
        if cls._TABLE is not None:
            return cls._TABLE
        cls._TABLE = [(raw, cls._decode_raw(raw)) for raw in range(1 << cls.N)]
        return cls._TABLE

    def __init__(self):
        # build sorted (value, raw) list of FINITE non-zero entries for bisect
        tbl = self._build_table()
        finite = [(v, r) for (r, v) in tbl if v is not None and v != 0]
        finite.sort()
        self._sorted_vals = [v for (v, _r) in finite]
        self._sorted_raws = [r for (v, r) in finite]

    def decode(self, raw):
        return self._decode_raw(raw)

    def encode(self, x):
        # Takum encoding from a real value is non-trivial (requires log/2 lookup).
        # For the benchmark we synthesize the encode by finding the raw code
        # whose decode (FP32-rounded) is closest to the input, via bisect on the
        # sorted finite-value table (which spans both signs, so negatives are
        # handled directly — note: takum's sign bit produces -exp(-(c+m)/2),
        # i.e. the negative reciprocal, so a naive sign-flip would be wrong).
        # This is exact up to the FP32 grid the format targets.
        if x == 0:
            return 0
        import bisect
        vals = self._sorted_vals
        raws = self._sorted_raws
        i = bisect.bisect_left(vals, x)
        candidates = []
        for j in (i - 1, i, i + 1):
            if 0 <= j < len(vals):
                candidates.append((abs(vals[j] - x), raws[j]))
        candidates.sort()
        return candidates[0][1]


def _exp_ell_half_to_fraction(ell, sign):
    """Compute exp(ell/2) rounded to binary32 RNE as an exact Fraction.

    Takum's tapered dynamic range exceeds float32; values outside the
    binary32 range map to +Inf (None), matching the t27 oracle's behavior.
    """
    import struct
    FLOAT32_MAX = 3.4028235e+38
    try:
        f = math.exp(float(ell) / 2.0)
    except OverflowError:
        return None  # +Inf
    except ValueError:
        return None
    if math.isnan(f):
        return None
    if f > FLOAT32_MAX:
        return None  # clamps to +Inf in binary32
    if f == 0.0:
        return Fraction(0)
    # snap to binary32 RNE
    packed = struct.pack('>f', f)
    f32 = struct.unpack('>f', packed)[0]
    if f32 == 0.0:
        return Fraction(0)
    return Fraction(f32) * (-1 if sign else 1)


takum16 = Takum16()


# =====================================================================
# Test-vector generators
# =====================================================================

def gen_arithmetic(n=1000, seed=42):
    """Random add/subtract pairs in [-100, 100]."""
    rng = random.Random(seed)
    for _ in range(n):
        a = Fraction(rng.uniform(-100, 100))
        b = Fraction(rng.uniform(-100, 100))
        op = rng.choice(["+", "-"])
        yield (a, b, op)


def gen_dynamic_range(n=200, seed=7):
    """Values spanning 10^-6 .. 10^6, paired for add."""
    rng = random.Random(seed)
    for _ in range(n):
        ea = rng.uniform(-6, 6)
        eb = rng.uniform(-6, 6)
        a = Fraction(10 ** ea)
        b = Fraction(10 ** eb)
        # rationalize: convert via float then Fraction (limit_denominator for exactness)
        a = Fraction(a).limit_denominator(10 ** 12)
        b = Fraction(b).limit_denominator(10 ** 12)
        yield (a, b, "+")


def gen_cancellation(n=200, seed=99):
    """Near-equal opposite-sign pairs that stress cancellation."""
    rng = random.Random(seed)
    for _ in range(n):
        base = rng.uniform(-100, 100)
        delta = rng.uniform(1e-6, 1e-2) * abs(base) if base != 0 else 1e-3
        a = Fraction(base).limit_denominator(10 ** 10)
        b = Fraction(-(base + delta)).limit_denominator(10 ** 10)
        yield (a, b, "+")


def gen_edge_cases():
    """Edge cases: 0, ±1, denormals, max-value of each format."""
    cases = [
        (Fraction(0), Fraction(1), "+"),
        (Fraction(0), Fraction(0), "+"),
        (Fraction(1), Fraction(-1), "+"),
        (Fraction(1), Fraction(-1), "-"),
        (Fraction("0.000001"), Fraction("0.000001"), "+"),
        (Fraction(100), Fraction(100), "+"),
        (Fraction(10, 1) ** 6, Fraction(1), "+"),
        (Fraction(1, 10 ** 6), Fraction(1, 10 ** 6), "+"),
        (Fraction(2).limit_denominator(), Fraction(3).limit_denominator(), "+"),
        (Fraction(-50), Fraction(50), "+"),
    ]
    return cases


SUITES = [
    ("arithmetic", gen_arithmetic()),
    ("dynamic_range", gen_dynamic_range()),
    ("cancellation", gen_cancellation()),
    ("edge_cases", gen_edge_cases()),
]

FORMATS = [gf16, gf12, posit16, mxfp8, bf16, fp16, takum16]


# =====================================================================
# Error measurement
# =====================================================================

def relative_error(exact: Fraction, approx):
    if exact == 0:
        return Fraction(0) if approx == 0 else None  # undefined
    if approx is None or approx == 0:
        # catastrophic: return a large penalty if exact != 0
        return None
    err = (exact - approx)
    if err < 0:
        err = -err
    return err / abs(exact)


def run_suite(name, pairs, fmts):
    """Run one suite across all formats. Returns dict[format_name] -> stats."""
    results = {f.name: {"count": 0, "sum": Fraction(0), "none_count": 0,
                        "max": Fraction(0), "overflow": 0} for f in fmts}
    for a, b, op in pairs:
        if op == "+":
            exact = a + b
        elif op == "-":
            exact = a - b
        else:
            continue
        for f in fmts:
            qa = f.quantize(a)
            qb = f.quantize(b)
            if qa is None or qb is None:
                results[f.name]["overflow"] += 1
                continue
            if op == "+":
                approx = qa + qb
            else:
                approx = qa - qb
            # approx is the exact sum of *quantized* operands; but the format's
            # arithmetic rounds the sum back. Re-quantize to model that rounding.
            approx_q = f.quantize(approx)
            if approx_q is None:
                results[f.name]["none_count"] += 1
                continue
            err = relative_error(exact, approx_q)
            results[f.name]["count"] += 1
            if err is None:
                results[f.name]["none_count"] += 1
            else:
                results[f.name]["sum"] += err
                if err > results[f.name]["max"]:
                    results[f.name]["max"] = err
    return results


def frac_to_sci_str(fr, none_label="n/a"):
    if fr is None:
        return none_label
    if fr == 0:
        return "0"
    f = float(fr)
    return f"{f:.4e}"


# =====================================================================
# Main
# =====================================================================

def main():
    print("=" * 92)
    print("Number-Format Accuracy Benchmark  —  Trinity catalog (2026-07-14)")
    print("Oracle: exact rational arithmetic (fractions.Fraction).")
    print("Formats differ in dynamic range; cross-format cells are illustrative,")
    print("not a controlled experiment. No superiority claim implied.")
    print("=" * 92)
    print()
    print("Formats:")
    for f in FORMATS:
        print(f"  {f.name:<16} {f.total_bits:>2}-bit   {f.layout}")
    print()

    csv_rows = []
    header = ["suite", "format", "layout", "n_valid", "n_invalid",
              "mean_rel_err", "max_rel_err"]
    csv_rows.append(header)

    for suite_name, pairs in SUITES:
        # materialize so each suite runs once
        pairs = list(pairs)
        print(f"--- Suite: {suite_name}  ({len(pairs)} cases) ---")
        results = run_suite(suite_name, pairs, FORMATS)
        col_w = [10, 14, 14, 12]
        print(f"{'format':<16}{'n_valid':>10}{'n_invalid':>10}"
              f"{'mean_rel_err':>16}{'max_rel_err':>16}")
        for f in FORMATS:
            r = results[f.name]
            n_valid = r["count"]
            n_invalid = r["none_count"] + r["overflow"]
            mean_err = (r["sum"] / n_valid) if n_valid else None
            max_err = r["max"]
            print(f"{f.name:<16}{n_valid:>10}{n_invalid:>10}"
                  f"{frac_to_sci_str(mean_err):>16}"
                  f"{frac_to_sci_str(max_err):>16}")
            csv_rows.append([suite_name, f.name, f.layout, n_valid, n_invalid,
                             frac_to_sci_str(mean_err),
                             frac_to_sci_str(max_err)])
        print()

    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "format_accuracy_results.csv")
    with open(csv_path, "w", newline="") as fp:
        w = csv.writer(fp)
        w.writerows(csv_rows)
    print(f"CSV written: {csv_path}")


if __name__ == "__main__":
    main()
