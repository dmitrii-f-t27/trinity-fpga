#!/usr/bin/env python3
"""Exact decode golden for the GF formats: code -> fp32 bit pattern.

The wide-GF decode hosts computed their golden like this:

    v = (1 + m / float(1 << M)) * (2.0 ** (e - BIAS))

which works for gf16 and breaks for everything above it. gf64 is
GF(64, E=24, M=39) with BIAS = 8388607, so `2.0 ** (e - BIAS)` reaches
`2.0 ** 8388607` at the top of its own test set and Python raises
OverflowError. research/audit_decode_host_goldens.py found four hosts that
cannot finish a run for this reason -- gf48, gf64, gf96 and gf128 -- each on an
exponent it picks for itself.

It also rounds twice: the format's significand goes through a 53-bit double and
then into a 24-bit fp32, where the format asks for one rounding.

This does it in integers. No float ever holds an intermediate.

ALL-ONES EXPONENT
-----------------
Only gf16 reserves exp=all-ones for Inf/NaN. For every other GF width it is a
FINITE maximum, and three independent sources say so:

  * the specs -- t27/specs/numeric/gf24.t27 and gf32.t27 define
    max_value() as mant_max * 2**((1 << EXP_BITS) - 1 - BIAS)
  * the oracle -- conformance/gf_ref.py, GFFormat.has_inf returns True only
    for gf16, citing gf8.t27:115-119 and gf20.t27:106-109
  * the RTL -- fpga/openxc7-synth/gf_adder_param.v, HAS_INF is a parameter and
    the comment reads "exp=all-ones is a FINITE max_value (gf8.t27:115-119) ->
    HAS_INF=0, overflow saturates to max-finite"

The hosts disagreed with all three. For a code with all-ones exponent and a
ZERO mantissa the disagreement is invisible -- the finite value is far past
fp32's range, so it overflows to +Inf, which is what the host returned anyway.
It shows up when the mantissa is NONZERO: the host called that NaN, while the
format says it is an ordinary finite number that also overflows to +Inf.

Anything that changes a golden changes what a PASS means. Decode cells recorded
against the old goldens were scored against the behaviour described above.
"""
from fractions import Fraction

# gf16 is the only GF width that reserves the all-ones exponent.
HAS_INF = {"gf16"}

FP32_INF = 0x7F800000
FP32_QNAN = 0x7FC00001


def gf_value(raw, N, E, M, BIAS, name=""):
    """Exact value of a GF code, as a Fraction -- or a ('inf'|'nan', sign) tag.

    Never materialises 2**(e - BIAS); the scale is carried as a separate power
    of two so a gf128 code costs the same as a gf16 one.
    Returns (kind, sign, significand, exp2) where the value is
    (-1)**sign * significand * 2**exp2 and significand is a Fraction in [0, 2).
    """
    raw &= (1 << N) - 1
    sign = raw >> (N - 1)
    e = (raw >> M) & ((1 << E) - 1)
    m = raw & ((1 << M) - 1)
    if e == (1 << E) - 1 and name in HAS_INF:
        return ("nan" if m else "inf"), sign, None, None
    if e == 0:
        if m == 0:
            return "zero", sign, None, None
        return "finite", sign, Fraction(m, 1 << M), 1 - BIAS
    return "finite", sign, Fraction((1 << M) + m, 1 << M), e - BIAS


def fp32_bits(kind, sign, sig, exp2):
    """Round an exact (significand, power of two) to fp32, once, ties-to-even."""
    if kind == "zero":
        return sign << 31
    if kind == "inf":
        return (sign << 31) | FP32_INF
    if kind == "nan":
        return FP32_QNAN

    # normalise the significand into [1, 2) without touching exp2's magnitude
    if sig == 0:
        return sign << 31
    shift = sig.numerator.bit_length() - sig.denominator.bit_length()
    if Fraction(sig) < Fraction(2) ** shift:
        shift -= 1
    sig = sig / Fraction(2) ** shift
    e = exp2 + shift                       # value = sig * 2**e, 1 <= sig < 2

    if e > 127:
        return (sign << 31) | FP32_INF
    if e < -150:
        return sign << 31

    if e >= -126:
        scaled = sig * (1 << 23)
        exp_field = e + 127
    else:
        scaled = sig * Fraction(2) ** (e + 149)     # into the 2**-149 grid
        exp_field = 0

    q, r = divmod(scaled.numerator, scaled.denominator)
    if r * 2 > scaled.denominator or (r * 2 == scaled.denominator and q & 1):
        q += 1
    if exp_field == 0:
        if q >= (1 << 23):
            return (sign << 31) | (1 << 23) | (q - (1 << 23))
        return (sign << 31) | q
    frac = q - (1 << 23)
    if frac >= (1 << 23):
        frac = 0
        exp_field += 1
        if exp_field >= 0xFF:
            return (sign << 31) | FP32_INF
    return (sign << 31) | (exp_field << 23) | frac


def decode_to_fp32(raw, N, E, M, BIAS, name=""):
    """The golden a GF decode host should use."""
    return fp32_bits(*gf_value(raw, N, E, M, BIAS, name))


def _self_test():
    checks = []
    # gf16 (E=6, M=9, BIAS=31) -- the one width WITH Inf/NaN
    checks += [
        ((0x0000, 16, 6, 9, 31, "gf16"), 0x00000000),          # +0
        ((0x8000, 16, 6, 9, 31, "gf16"), 0x80000000),          # -0
        (((31 << 9), 16, 6, 9, 31, "gf16"), 0x3F800000),       # 1.0
        (((32 << 9), 16, 6, 9, 31, "gf16"), 0x40000000),       # 2.0
        (((63 << 9), 16, 6, 9, 31, "gf16"), 0x7F800000),       # all-ones, m=0 -> Inf
        (((63 << 9) | 1, 16, 6, 9, 31, "gf16"), FP32_QNAN),    # all-ones, m!=0 -> NaN
    ]
    # gf24 (E=9, M=14, BIAS=255) -- all-ones is FINITE, and overflows fp32
    checks += [
        (((255 << 14), 24, 9, 14, 255, "gf24"), 0x3F800000),   # 1.0
        (((511 << 14), 24, 9, 14, 255, "gf24"), 0x7F800000),   # finite, overflows
        (((511 << 14) | 1, 24, 9, 14, 255, "gf24"), 0x7F800000),  # NOT NaN
    ]
    # gf64 -- the host that raised OverflowError here
    checks += [
        (((8388607 << 39), 64, 24, 39, 8388607, "gf64"), 0x3F800000),   # 1.0
        (((16777214 << 39), 64, 24, 39, 8388607, "gf64"), 0x7F800000),  # was OverflowError
        (((1 << 39), 64, 24, 39, 8388607, "gf64"), 0x00000000),         # underflows to 0
    ]
    bad = 0
    for args, want in checks:
        got = decode_to_fp32(*args)
        if got != want:
            bad += 1
            print("FAIL %s -> %#010x want %#010x" % (args, got, want))
    print("gf_decode_golden SELF-TEST: %s (%d/%d)"
          % ("PASS" if bad == 0 else "FAIL", len(checks) - bad, len(checks)))
    return bad == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if _self_test() else 1)
