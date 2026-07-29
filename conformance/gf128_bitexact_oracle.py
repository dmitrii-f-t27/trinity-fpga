#!/usr/bin/env python3
"""gf128 STRICT bit-exact oracle -- GF(128, E=49, M=78, BIAS=281474976710655) -> IEEE-754 binary64.

Purpose (Trinity Catalog-100, horizon-A SW axis):
  Promote gf128 from `bitexact_selfconsistent` (the existing FP32-truncating
  conformance `gf128_decode_conformance_ax7203.py` -- one decode law, no 2nd
  witness, AND it TRUNCATES the 78-bit mantissa to 23 FP32 bits) to STRICT
  SW-bitexact: independent decoder + abs_error==0 vs a 2nd independent witness.

Continuation of the gf48 / gf96 technique (commits c3ab8264 / 1a7fde6c), now
HARDER than gf96 because M=78:
  * 78 - 52 = 26 mantissa bits must be ROUNDED (round-to-nearest-even) on every
    normal decode (gf96 rounded 7; gf48 rounded 0). All 3 witnesses implement
    the 78->52 RNE independently.
  * BIAS = 2^48 - 1 -> 48-bit Verilog localparam; witness A on mpmath
    (fractions.Fraction would materialize 2^(+-2.8e14) -- impossible).
  * exponent range +-2^48 vs binary64 +-1023/1074 -> almost all codes map to
    +/-inf or +/-0; only the e ~= BIAS window produces finite nonzero output,
    and only there can the 78->52 rounding bite.

Three independent witnesses (honesty requirement, inv. #10 / catalog rule 5):
  (A) EXACT mpmath mpf (dps=80 >> 78 bits -> every dyadic input exact) -> binary64
      via frexp + scaling + RNE half-comparison (NO guard/sticky bits).
  (B) Pure integer field-by-field construction (mirrors the RTL datapath),
      guard/sticky bit extraction for the 78->52 rounding; the huge gf128
      exponent range never materializes a big integer (pure add/sub bookkeeping).
  (C) RTL `gf128_decode_fp64.v` via iverilog (fixed-width, catches width/OOB
      bugs a python arbitrary-width transcription cannot, inv. #6).
  A == B == C over representative + boundary + random sweep -> 3 witnesses.

Author: Vasilev (gHashTag), ORCID 0009-0008-4294-6159, admin@t27.ai.
"""
import mpmath
import os
import sys

mpmath.mp.dps = 100   # >> 78 mantissa bits -> every dyadic input value is exact

N, E, M, BIAS = 128, 49, 78, 281474976710655      # BIAS = 2^48 - 1
EMASK = (1 << E) - 1
MMASK = (1 << M) - 1
EMAX = EMASK

# binary64 field constants
FP64_EBIAS = 1023
FP64_MANT = 52
FP64_EMAX = 2047
FP64_MAX_EXP = 1024
FP64_MIN_NORM_EXP = -1022
FP64_SUB_LSB_EXP = -1074

QNAN64 = 0x7FF8000000000001
POS_INF64 = 0x7FF0000000000000
NEG_INF64 = 0xFFF0000000000000
MMASK_52 = (1 << FP64_MANT) - 1


def gf128_fields(raw):
    raw &= (1 << N) - 1
    s = raw >> (N - 1)
    e = (raw >> M) & EMASK
    m = raw & MMASK
    return s, e, m


# ---------------------------------------------------------------------------
# Witness A: EXACT mpmath value, then correctly-rounded binary64 via frexp +
# scaling + exact RNE half-comparison (NO guard/sticky bits).
# ---------------------------------------------------------------------------
def _mpf_rne_round_to_grid(val, lsb_exp):
    units = val * mpmath.power(2, -lsb_exp)
    fl = mpmath.floor(units)
    fl_i = int(fl)
    rem = units - fl
    half = mpmath.mpf(1) / 2
    if rem > half:
        return fl_i + 1
    if rem == half:
        return fl_i + (1 if (fl_i & 1) else 0)
    return fl_i


def mpf_to_binary64(val):
    sign = 1 if val < 0 else 0
    a = mpmath.fabs(val)
    _frac, e2 = mpmath.frexp(a)
    E2 = e2 - 1
    if E2 >= FP64_MAX_EXP:
        return NEG_INF64 if sign else POS_INF64
    if E2 >= FP64_MIN_NORM_EXP:
        mant53 = _mpf_rne_round_to_grid(a, E2 - FP64_MANT)
        if mant53 == (1 << 53):
            mant53 >>= 1
            E2 += 1
            if E2 >= FP64_MAX_EXP:
                return NEG_INF64 if sign else POS_INF64
        exp_field = E2 + FP64_EBIAS
        if exp_field >= FP64_EMAX:
            return NEG_INF64 if sign else POS_INF64
        return (sign << 63) | (exp_field << FP64_MANT) | (mant53 & MMASK_52)
    mant = _mpf_rne_round_to_grid(a, FP64_SUB_LSB_EXP)
    if mant == 0:
        return sign << 63
    if mant >= (1 << FP64_MANT):
        return (sign << 63) | (1 << FP64_MANT)
    return (sign << 63) | mant


def witness_A(raw):
    s, e, m = gf128_fields(raw)
    if e == EMAX:
        if m == 0:
            return NEG_INF64 if s else POS_INF64
        return QNAN64
    if e == 0 and m == 0:
        return s << 63
    if e == 0:
        val = mpmath.mpf(m) * mpmath.power(2, 1 - BIAS - M)
    else:
        val = (mpmath.mpf(1) + mpmath.mpf(m) / mpmath.power(2, M)) * mpmath.power(2, e - BIAS)
    if s:
        val = -val
    return mpf_to_binary64(val)


# ---------------------------------------------------------------------------
# Witness B: field-by-field INTEGER construction (mirrors RTL datapath),
# NO mpmath, NO Fraction. Guard/sticky for 78->52. value = full_sig * 2^(E2-M),
# full_sig has (M+1)=79 bits, top set, E2 = floor(log2(value)).
# ---------------------------------------------------------------------------
def witness_B(raw):
    s, e, m = gf128_fields(raw)
    if e == EMAX:
        if m == 0:
            return NEG_INF64 if s else POS_INF64
        return QNAN64
    if e == 0 and m == 0:
        return s << 63
    if e == 0:
        lz = M - m.bit_length()
        true_exp = (1 - BIAS) - (lz + 1)
        frac_field = (m << (lz + 1)) & MMASK
    else:
        true_exp = e - BIAS
        frac_field = m

    full_sig = (1 << M) | frac_field
    sigbits = M + 1                                 # 79
    E2 = true_exp

    if E2 >= FP64_MAX_EXP:
        return NEG_INF64 if s else POS_INF64

    if E2 >= FP64_MIN_NORM_EXP:
        # binary64 normal: round 79-bit full_sig to 53 significant bits (drop 26).
        drop = sigbits - 53                         # 26 for gf128
        kept = full_sig >> drop
        dropped = full_sig - (kept << drop)
        half = 1 << (drop - 1)
        if dropped > half or (dropped == half and (kept & 1)):
            kept += 1
        if kept == (1 << 53):
            kept >>= 1
            E2 += 1
            if E2 >= FP64_MAX_EXP:
                return NEG_INF64 if s else POS_INF64
        exp_field = E2 + FP64_EBIAS
        if exp_field >= FP64_EMAX:
            return NEG_INF64 if s else POS_INF64
        return (s << 63) | (exp_field << FP64_MANT) | (kept & MMASK_52)

    # binary64 subnormal / underflow (E2 <= -1023).
    # value = full_sig * 2^(E2-M); units of 2^-1074 -> sh = -(E2-M+1074) = -E2+M-1074
    sh = -(E2 - M + 1074)
    if sh > sigbits:                                # sh >= 80 -> underflow to 0
        return s << 63
    mant = full_sig >> sh
    dropped = full_sig - (mant << sh)
    half = 1 << (sh - 1)
    if dropped > half or (dropped == half and (mant & 1)):
        mant += 1
    if mant == 0:
        return s << 63
    if mant >= (1 << FP64_MANT):
        return (s << 63) | (1 << FP64_MANT)
    return (s << 63) | mant


# ---------------------------------------------------------------------------
# Representative + boundary + deterministic-random sweep.
# ---------------------------------------------------------------------------
def sample_codes():
    codes = set()
    MMAX = MMASK
    for s in (0, 1):
        base = s << (N - 1)
        codes.add(base)                                  # +-0
        codes.add(base | (EMAX << M))                    # +-inf
        codes.add(base | (EMAX << M) | 1)                # nan
        codes.add(base | (EMAX << M) | MMAX)             # nan
        for mv in (1, MMAX, MMAX // 2, 1 << (M - 1), (1 << (M - 1)) - 1, 3, 0x7F):
            codes.add(base | mv)

    # finite-nonzero binary64 lives only where |true_exp| <= ~1074 (e ~= BIAS).
    exp_samples = set()
    for de in range(-1130, 1075):
        ce = BIAS + de
        if 1 <= ce < EMAX:
            exp_samples.add(ce)
    for boundary in (1024, 1023, 1022, -1022, -1023, -1074, -1075, -1076):
        ce = BIAS + boundary
        if 1 <= ce < EMAX:
            exp_samples.add(ce)
    # mantissas stressing the low 26 rounded-away bits
    mant_reps = [
        0, MMAX, MMAX // 2, 1, 1 << (M - 1), (1 << (M - 1)) - 1,
        MMAX - 1, 0x3FFFFFF, 0x2000000, 0x1FFFFFF,          # patterns in the low 26 bits
        (MMASK >> 26) << 26, (MMASK >> 26) << 26 | 0x1FFFFFF,
    ]
    for s in (0, 1):
        base = s << (N - 1)
        for e in sorted(exp_samples):
            for mv in mant_reps:
                codes.add(base | (e << M) | mv)

    # far field -> exercise inf / 0 classes
    far = set()
    for e in (1, 2, 3, 100, 1000, 1 << 20, 1 << 30, EMAX - 1, EMAX - 2,
              BIAS - (1 << 30), BIAS - (1 << 20), BIAS - 1000, BIAS - 100):
        if 1 <= e < EMAX:
            far.add(e)
    for s in (0, 1):
        base = s << (N - 1)
        for e in sorted(far):
            for mv in (0, MMAX, MMAX // 2, 1, 0x3FFFFFF):
                codes.add(base | (e << M) | mv)

    import random
    rng = random.Random(20260725)
    for _ in range(6000):
        codes.add(rng.randrange(1 << N))
    return sorted(codes)


def main():
    codes = sample_codes()
    mism_ab = 0
    dump = []
    for raw in codes:
        a = witness_A(raw)
        b = witness_B(raw)
        a_is_nan = ((a >> 52) & 0x7FF) == 0x7FF and (a & MMASK_52) != 0
        b_is_nan = ((b >> 52) & 0x7FF) == 0x7FF and (b & MMASK_52) != 0
        ok = (a == b) or (a_is_nan and b_is_nan)
        if not ok:
            if mism_ab < 20:
                s, e, m = gf128_fields(raw)
                print(f"  A!=B raw={raw:#034x} (s={s} e={e} m={m:#022x}) "
                      f"A={a:#018x} B={b:#018x}", file=sys.stderr)
            mism_ab += 1
        dump.append((raw, a))
    print(f"WITNESS CROSS-CHECK (A mpmath-exact vs B integer-construct): "
          f"{len(codes)-mism_ab}/{len(codes)} agree (mismatch={mism_ab})")
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gf128_vectors.hex")
    with open(out_path, "w") as f:
        for raw, exp in dump:
            f.write(f"{raw:032x} {exp:016x}\n")     # 128-bit raw = 32 nybbles
    print(f"Wrote {len(dump)} vectors to gf128_vectors.hex")
    return 0 if mism_ab == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
