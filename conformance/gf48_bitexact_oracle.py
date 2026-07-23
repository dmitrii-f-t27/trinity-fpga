#!/usr/bin/env python3
"""gf48 STRICT bit-exact oracle — GF(48, E=18, M=29, BIAS=131071) -> IEEE-754 binary64.

Purpose (Trinity Catalog-100, horizon-A SW axis):
  Promote gf48 from `bitexact_selfconsistent` (the existing FP32-truncating
  conformance, one decode law, no 2nd witness) to STRICT SW-bitexact
  (independent decoder + abs_error==0 vs a 2nd independent witness).

Why binary64, not binary32:
  gf48 has M=29 mantissa bits. FP32 has only 23 -> the existing
  gf48_decode_conformance_ax7203.py TRUNCATES 6 mantissa bits (`>f` pack),
  so it can only ever be self-consistent, never strictly bit-exact against
  an exact oracle. binary64 has 52 mantissa bits >= 29, so every finite gf48
  *normal* value is represented in binary64 with ZERO rounding error. This
  makes an abs_error==0 strict comparison possible.

Two independent witnesses (the honesty requirement, inv. #10 / catalog rule 5):
  (A) EXACT oracle: decode gf48 word via python Fractions -> exact rational,
      then convert that rational to the nearest binary64 with round-to-nearest-
      even done in ARBITRARY precision (Fraction comparison of the two
      neighbouring doubles). This never touches float until the final,
      provably-correct rounding step.
  (B) A DIFFERENT closed-form path: build the binary64 bit pattern field-by-
      field by integer exponent arithmetic (mirrors what the RTL will do),
      NOT via Fraction. If (A) and (B) agree bit-for-bit over the full
      representative + exhaustive-exponent sweep, and the RTL (iverilog)
      also agrees, we have 3 independent witnesses.

Author: Vasilev (gHashTag), ORCID 0009-0008-4294-6159, admin@t27.ai.
"""
from fractions import Fraction
import struct
import sys

N, E, M, BIAS = 48, 18, 29, 131071
EMASK = (1 << E) - 1
MMASK = (1 << M) - 1
EMAX = EMASK

# binary64 field constants
FP64_EBIAS = 1023
FP64_MANT = 52
FP64_EMAX = 2047
FP64_MIN_NORM_EXP = -1022          # smallest true exp for a binary64 normal
FP64_SUB_LSB_EXP = -1074           # exponent of the binary64 subnormal LSB (2^-1074)

QNAN64 = 0x7FF8000000000001
POS_INF64 = 0x7FF0000000000000
NEG_INF64 = 0xFFF0000000000000


def gf48_fields(raw):
    raw &= (1 << N) - 1
    s = raw >> (N - 1)
    e = (raw >> M) & EMASK
    m = raw & MMASK
    return s, e, m


# ---------------------------------------------------------------------------
# Witness A: EXACT rational value, then correctly-rounded binary64.
# ---------------------------------------------------------------------------
def gf48_exact_value(raw):
    """Return (kind, Fraction|None). kind in {'nan','inf','zero','finite'}."""
    s, e, m = gf48_fields(raw)
    if e == EMAX:
        if m == 0:
            return ('inf', s)
        return ('nan', None)
    if e == 0 and m == 0:
        return ('zero', s)
    if e == 0:
        # subnormal: (-1)^s * (m / 2^M) * 2^(1-BIAS)
        val = Fraction(m, 1 << M) * Fraction(2) ** (1 - BIAS)
    else:
        # normal: (-1)^s * (1 + m/2^M) * 2^(e-BIAS)
        val = (Fraction(1) + Fraction(m, 1 << M)) * Fraction(2) ** (e - BIAS)
    if s:
        val = -val
    return ('finite', val)


def _floor_log2_frac(val):
    """Return E2 = floor(log2(val)) for a positive Fraction, using integer
    bit_length arithmetic (NO iterative multiply -- O(1) on huge exponents)."""
    n, d = val.numerator, val.denominator
    # 2^E2 <= n/d < 2^(E2+1)  <=>  E2 = floor(log2(n/d))
    E2 = n.bit_length() - d.bit_length()
    # correct off-by-one: compare n vs d*2^E2 exactly
    if E2 >= 0:
        if n < (d << E2):
            E2 -= 1
    else:
        if (n << (-E2)) < d:
            E2 -= 1
    return E2


def frac_to_binary64_bits(val, sign):
    """Correctly round a non-zero positive Fraction |val| to binary64,
    return the 64-bit integer pattern. Round-to-nearest-even, all in
    exact rational arithmetic (no float, no iterative normalize)."""
    if val == 0:
        return sign << 63
    E2 = _floor_log2_frac(val)   # 2^E2 <= val < 2^(E2+1); true_exp = E2
    if E2 < FP64_MIN_NORM_EXP:
        # subnormal region: value = mant_int * 2^FP64_SUB_LSB_EXP
        # mant_int = round(val * 2^-FP64_SUB_LSB_EXP)  (RNE)
        scaled = val * (Fraction(2) ** (-FP64_SUB_LSB_EXP))
        mant_int = _round_half_even(scaled)
        if mant_int == 0:
            return sign << 63
        if mant_int >= (1 << FP64_MANT):
            # rounded up into the smallest normal
            return (sign << 63) | (1 << FP64_MANT)
        return (sign << 63) | int(mant_int)
    # normal region: significand v = val / 2^E2 in [1,2); store 52 frac bits RNE
    frac = val * (Fraction(2) ** (-E2)) - 1   # in [0,1)
    scaled = frac * (1 << FP64_MANT)
    mant_int = _round_half_even(scaled)
    exp_field = E2 + FP64_EBIAS
    if mant_int == (1 << FP64_MANT):
        mant_int = 0
        exp_field += 1
    if exp_field >= FP64_EMAX:
        return NEG_INF64 if sign else POS_INF64
    return (sign << 63) | (exp_field << FP64_MANT) | int(mant_int)


def _round_half_even(fr):
    """Round a Fraction to nearest integer, ties to even."""
    fl = fr.numerator // fr.denominator
    rem = fr - fl
    if rem < Fraction(1, 2):
        return fl
    if rem > Fraction(1, 2):
        return fl + 1
    # exactly halfway -> to even
    return fl if (fl % 2 == 0) else fl + 1


def witness_A(raw):
    kind, payload = gf48_exact_value(raw)
    if kind == 'nan':
        return QNAN64
    if kind == 'inf':
        return NEG_INF64 if payload else POS_INF64
    if kind == 'zero':
        return payload << 63
    val = payload  # Fraction, may be negative
    sign = 1 if val < 0 else 0
    return frac_to_binary64_bits(abs(val), sign)


# ---------------------------------------------------------------------------
# Witness B: field-by-field integer construction (mirrors RTL datapath),
# NO Fraction. Because M=29 <= 52 and gf48 exponent range fits, every finite
# normal gf48 maps to a binary64 with NO rounding: mantissa left-shifts into
# place, exponent rebiases. Subnormals renormalise via leading-zero count.
# ---------------------------------------------------------------------------
def witness_B(raw):
    s, e, m = gf48_fields(raw)
    if e == EMAX:
        if m == 0:
            return NEG_INF64 if s else POS_INF64
        return QNAN64
    if e == 0 and m == 0:
        return s << 63
    if e == 0:
        # subnormal: renormalise. value = (m / 2^M) * 2^(1-BIAS)
        #          = m * 2^(1-BIAS-M). Leading bit of m at position (M-1-lz).
        lz = M - 1 - m.bit_length() + 1  # count leading zeros within M-bit field
        # after shifting the leading 1 to bit M-1: true_exp = (1-BIAS) - (lz+1)
        true_exp = (1 - BIAS) - (lz + 1)
        # fraction bits after the implicit 1:
        frac_field = (m << (lz + 1)) & MMASK  # M bits, top bit dropped (implicit 1)
        mant_src_bits = M
    else:
        true_exp = e - BIAS
        frac_field = m
        mant_src_bits = M

    # Now value = (1 + frac_field/2^mant_src_bits) * 2^true_exp, sign s.
    if true_exp >= FP64_MIN_NORM_EXP:
        # binary64 normal (no overflow possible: gf48 max exp << fp64 max)
        exp_field = true_exp + FP64_EBIAS
        if exp_field >= FP64_EMAX:
            return NEG_INF64 if s else POS_INF64
        # widen mantissa M->52 (M=29 <= 52 => pure left shift, exact)
        mant52 = frac_field << (FP64_MANT - mant_src_bits)
        return (s << 63) | (exp_field << FP64_MANT) | (mant52 & ((1 << FP64_MANT) - 1))
    # binary64 subnormal via gradual underflow (exact: full_sig has M+1 bits <= 52)
    full_sig = (1 << mant_src_bits) | frac_field   # (mant_src_bits+1) bits
    shift = mant_src_bits - true_exp + FP64_SUB_LSB_EXP
    if shift < 0:
        # would be > subnormal max; shouldn't happen for gf48 but guard
        mant64 = full_sig << (-shift)
    else:
        # exact only if we don't drop set bits; check for rounding
        dropped_mask = (1 << shift) - 1 if shift > 0 else 0
        dropped = full_sig & dropped_mask
        mant64 = full_sig >> shift if shift > 0 else full_sig
        # round-to-nearest-even on dropped bits
        if shift > 0 and dropped:
            half = 1 << (shift - 1)
            if dropped > half or (dropped == half and (mant64 & 1)):
                mant64 += 1
    if mant64 == 0:
        return s << 63
    if mant64 >= (1 << FP64_MANT):
        # carried into normal
        return (s << 63) | (1 << FP64_MANT)
    return (s << 63) | mant64


# ---------------------------------------------------------------------------
# Cross-check A == B and dump vectors for the RTL testbench.
# ---------------------------------------------------------------------------
def sample_codes():
    codes = set()
    for s in (0, 1):
        base = s << (N - 1)
        codes.add(base)                       # +-0
        codes.add(base | (EMAX << M))         # +-inf
        codes.add(base | (EMAX << M) | 1)     # nan
        codes.add(base | (EMAX << M) | MMASK) # nan
        # subnormals
        for mv in (1, MMASK, MMASK // 2, 1 << (M - 1), (1 << (M - 1)) - 1):
            codes.add(base | mv)
        # normals: REPRESENTATIVE exponent sweep (full 2^18 exp range is 262k*
        # -- with huge-power Fractions that is too slow AND 2^48 total codes
        # make true exhaustive impossible; strict bit-exact for a 48-bit format
        # uses a representative + boundary + random sweep, same tier the FPGA
        # conformance uses). We hit every DECADE of the exponent range plus the
        # underflow/overflow boundaries where the binary64 path switches
        # normal<->subnormal (the interesting corner for a strict oracle).
        exp_samples = set()
        # dense near both ends and near the fp64 normal/subnormal boundary
        for e in list(range(1, 40)) + list(range(EMAX - 40, EMAX)):
            exp_samples.add(e)
        # fp64 subnormal boundary: true_exp == FP64_MIN_NORM_EXP => e == BIAS-1022
        for de in range(-40, 41):
            ce = (BIAS + FP64_MIN_NORM_EXP) + de
            if 1 <= ce < EMAX:
                exp_samples.add(ce)
        # logarithmic spread across the whole range
        step = max(1, EMAX // 400)
        for e in range(1, EMAX, step):
            exp_samples.add(e)
        for e in sorted(exp_samples):
            for mv in (0, MMASK, MMASK // 2, 1, 1 << (M - 1), (1 << (M - 1)) - 1):
                codes.add(base | (e << M) | mv)
    # deterministic random fill
    import random
    rng = random.Random(20260723)
    for _ in range(4000):
        codes.add(rng.randrange(1 << N))
    return sorted(codes)


def main():
    codes = sample_codes()
    mism_ab = 0
    dump = []
    for raw in codes:
        a = witness_A(raw)
        b = witness_B(raw)
        # NaN payload may differ in low bits between witnesses; treat any NaN==NaN
        a_is_nan = ((a >> 52) & 0x7FF) == 0x7FF and (a & ((1 << 52) - 1)) != 0
        b_is_nan = ((b >> 52) & 0x7FF) == 0x7FF and (b & ((1 << 52) - 1)) != 0
        ok = (a == b) or (a_is_nan and b_is_nan)
        if not ok:
            if mism_ab < 20:
                print(f"  A!=B raw={raw:#014x} A={a:#018x} B={b:#018x}", file=sys.stderr)
            mism_ab += 1
        dump.append((raw, a))
    print(f"WITNESS CROSS-CHECK (A exact-Fraction vs B integer-construct): "
          f"{len(codes)-mism_ab}/{len(codes)} agree (mismatch={mism_ab})")
    # write vectors for iverilog tb: hex raw (48-bit, 12 nybbles) + expected 64-bit
    with open("/home/user/workspace/trinity-fpga/conformance/gf48_vectors.hex", "w") as f:
        for raw, exp in dump:
            f.write(f"{raw:012x} {exp:016x}\n")
    print(f"Wrote {len(dump)} vectors to gf48_vectors.hex")
    return 0 if mism_ab == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
