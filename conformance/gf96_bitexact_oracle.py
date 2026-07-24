#!/usr/bin/env python3
"""gf96 STRICT bit-exact oracle -- GF(96, E=36, M=59, BIAS=34359738367) -> IEEE-754 binary64.

Purpose (Trinity Catalog-100, horizon-A SW axis):
  Promote gf96 from `bitexact_selfconsistent` (the existing FP32-truncating
  conformance `gf96_decode_conformance_ax7203.py` -- one decode law, no 2nd
  witness, AND it TRUNCATES the 59-bit mantissa to 23 FP32 bits) to STRICT
  SW-bitexact: independent decoder + abs_error==0 vs a 2nd independent witness.

Why binary64, not binary32:
  gf96 has M=59 mantissa bits. FP32 stores only 23 -> the existing conformance
  TRUNCATES 36 mantissa bits, so it can only ever be self-consistent. binary64
  stores 52 mantissa bits: 59-52 = 7 bits STILL must be rounded (unlike gf48,
  where M=29 <= 52 needed zero rounding). This file therefore exercises the
  round-to-nearest-even of those 7 extra bits in THREE independent ways.

Why mpmath (not fractions.Fraction) as the EXACT witness A:
  gf96 BIAS = 34359738367 (= 2^35 - 1). The exact value
  (1 + m/2^59) * 2^(e-BIAS) involves the power 2^(e-BIAS), whose exponent can
  reach +/-3.4e10. `fractions.Fraction(2)**k` MATERIALIZES the full integer
  (2^3.4e10 ~= 10^10 decimal digits ~= 10 GB per number) -- infeasible.
  mpmath stores a binary float as (man, exp) with exp a plain Python int, so
  2^3.4e10 is O(1). At dps=80 (>>59 mantissa bits) every dyadic input value is
  represented EXACTLY, and the only approximation is the final, provably-correct
  RNE rounding to binary64 done via scaling + floor + exact half comparison.

Three independent witnesses (honesty requirement, inv. #10 / catalog rule 5):
  (A) EXACT oracle via mpmath arbitrary-precision float: decode gf96 word to an
      exact mpf, then round to the nearest binary64 via frexp + scaling to a
      [2^52, 2^53) integer grid + RNE half-comparison -- NO guard/sticky bits.
  (B) A DIFFERENT closed-form path: pure integer field-by-field construction
      (mirrors the RTL datapath), using guard/sticky bit extraction for the
      59->52 rounding and a wide signed exponent. NO mpmath, NO Fraction.
  (C) RTL `gf96_decode_fp64.v` via iverilog (fixed-width, catches truncation /
      OOB / width bugs that a python arbitrary-width transcription cannot,
      inv. #6).
  If A == B == C over the representative + boundary + random sweep, that is
  three independent witnesses and the strict SW-bitexact tier holds.

Range note (gf96 exponent range is astronomically larger than binary64):
  gf96 true_exp spans +/-2^35 ~= +/-3.4e10, vs binary64's +/-1023/1074. Hence
  the vast majority of gf96 codes map to +/-inf (overflow) or +/-0 (underflow)
  in binary64. Only codes with |true_exp| <= ~1074 produce finite nonzero
  binary64, and ONLY THERE can the 59->52 mantissa rounding actually matter.
  The sweep therefore samples the e ~= BIAS window densely (where finite
  binary64 lives) PLUS the far field (to exercise the inf/0 class transitions)
  PLUS the exact binary64 normal/subnormal/inf/zero boundaries.

Author: Vasilev (gHashTag), ORCID 0009-0008-4294-6159, admin@t27.ai.
"""
import mpmath
import sys

mpmath.mp.dps = 80   # >> 59 mantissa bits -> every dyadic input value is exact

N, E, M, BIAS = 96, 36, 59, 34359738367
EMASK = (1 << E) - 1
MMASK = (1 << M) - 1
EMAX = EMASK

# binary64 field constants
FP64_EBIAS = 1023
FP64_MANT = 52
FP64_EMAX = 2047              # exponent field of inf/nan
FP64_MAX_EXP = 1024           # true floor-log2 >= 1024  -> overflow to inf
FP64_MIN_NORM_EXP = -1022     # smallest true exp for a binary64 normal
FP64_SUB_LSB_EXP = -1074      # exponent of the binary64 subnormal LSB (2^-1074)

QNAN64 = 0x7FF8000000000001
POS_INF64 = 0x7FF0000000000000
NEG_INF64 = 0xFFF0000000000000


def gf96_fields(raw):
    raw &= (1 << N) - 1
    s = raw >> (N - 1)
    e = (raw >> M) & EMASK
    m = raw & MMASK
    return s, e, m


# ---------------------------------------------------------------------------
# Witness A: EXACT mpmath value, then correctly-rounded binary64 via
# frexp + scaling + exact RNE half-comparison (NO guard/sticky bits).
# ---------------------------------------------------------------------------
def _mpf_rne_round_to_grid(val, lsb_exp):
    """Round a NON-NEGATIVE mpf `val` to the nearest integer multiple of
    2^lsb_exp, ties-to-even, using mpmath floor + exact half comparison.
    Returns the integer multiple (a Python int)."""
    units = val * mpmath.power(2, -lsb_exp)        # = val / 2^lsb_exp, exact
    fl = mpmath.floor(units)
    fl_i = int(fl)
    rem = units - fl                                 # in [0,1), exact
    half = mpmath.mpf(1) / 2
    if rem > half:
        return fl_i + 1
    if rem == half:
        return fl_i + (1 if (fl_i & 1) else 0)      # ties to even
    return fl_i


def mpf_to_binary64(val):
    """Correctly round a signed nonzero finite mpf to binary64 (RNE).
    Returns the 64-bit integer pattern."""
    sign = 1 if val < 0 else 0
    a = mpmath.fabs(val)
    # floor(log2(a)) via frexp (exact for dyadic mpf, handles huge exponents)
    _frac, e2 = mpmath.frexp(a)                      # a = frac*2^e2, frac in [0.5,1)
    E2 = e2 - 1                                       # floor(log2(a))
    if E2 >= FP64_MAX_EXP:
        return NEG_INF64 if sign else POS_INF64
    if E2 >= FP64_MIN_NORM_EXP:
        # binary64 normal: significand in [1,2) -> keep 53 bits.
        # value = significand * 2^E2; LSB kept at 2^(E2-52).
        mant53 = _mpf_rne_round_to_grid(a, E2 - FP64_MANT)
        if mant53 == (1 << 53):                       # rounded up across binade
            mant53 >>= 1
            E2 += 1
            if E2 >= FP64_MAX_EXP:
                return NEG_INF64 if sign else POS_INF64
        exp_field = E2 + FP64_EBIAS
        if exp_field >= FP64_EMAX:
            return NEG_INF64 if sign else POS_INF64
        return (sign << 63) | (exp_field << FP64_MANT) | (mant53 & MMASK_52)
    # subnormal / underflow region: LSB at 2^FP64_SUB_LSB_EXP
    mant = _mpf_rne_round_to_grid(a, FP64_SUB_LSB_EXP)
    if mant == 0:
        return sign << 63
    if mant >= (1 << FP64_MANT):                      # carried into smallest normal
        return (sign << 63) | (1 << FP64_MANT)        # exp_field = 1, mant = 0
    return (sign << 63) | mant


MMASK_52 = (1 << FP64_MANT) - 1


def witness_A(raw):
    s, e, m = gf96_fields(raw)
    if e == EMAX:
        if m == 0:
            return NEG_INF64 if s else POS_INF64
        return QNAN64
    if e == 0 and m == 0:
        return s << 63
    if e == 0:
        # subnormal: value = m * 2^(1-BIAS-M)
        val = mpmath.mpf(m) * mpmath.power(2, 1 - BIAS - M)
    else:
        # normal: value = (1 + m/2^M) * 2^(e-BIAS)
        val = (mpmath.mpf(1) + mpmath.mpf(m) / mpmath.power(2, M)) * mpmath.power(2, e - BIAS)
    if s:
        val = -val
    return mpf_to_binary64(val)


# ---------------------------------------------------------------------------
# Witness B: field-by-field INTEGER construction (mirrors RTL datapath),
# NO mpmath, NO Fraction. Guard/sticky bit extraction for the 59->52 rounding.
# value = full_sig * 2^(E2 - M), full_sig has (M+1)=60 bits, top bit set,
# E2 = floor(log2(value)).  The exponent bookkeeping is pure integer add/sub,
# so the huge gf96 exponent range never materializes a big integer.
# ---------------------------------------------------------------------------
def witness_B(raw):
    s, e, m = gf96_fields(raw)
    if e == EMAX:
        if m == 0:
            return NEG_INF64 if s else POS_INF64
        return QNAN64
    if e == 0 and m == 0:
        return s << 63
    if e == 0:
        # subnormal: renormalise within the M-bit field (inherited gf48 law).
        lz = M - m.bit_length()                  # leading zeros in M-bit field
        true_exp = (1 - BIAS) - (lz + 1)
        frac_field = (m << (lz + 1)) & MMASK     # implicit-1 shifted out of M-bit field
    else:
        true_exp = e - BIAS
        frac_field = m

    full_sig = (1 << M) | frac_field             # 60 bits, top set
    sigbits = M + 1                              # 60
    E2 = true_exp                                # significand normalised to [1,2)

    if E2 >= FP64_MAX_EXP:
        return NEG_INF64 if s else POS_INF64

    if E2 >= FP64_MIN_NORM_EXP:
        # binary64 normal: round 60-bit full_sig to 53 significant bits (drop 7).
        drop = sigbits - 53                      # 7 for gf96
        kept = full_sig >> drop
        dropped = full_sig - (kept << drop)
        half = 1 << (drop - 1)
        if dropped > half or (dropped == half and (kept & 1)):
            kept += 1
        if kept == (1 << 53):                    # rounded up across the binade
            kept >>= 1
            E2 += 1
            if E2 >= FP64_MAX_EXP:
                return NEG_INF64 if s else POS_INF64
        exp_field = E2 + FP64_EBIAS
        if exp_field >= FP64_EMAX:
            return NEG_INF64 if s else POS_INF64
        return (s << 63) | (exp_field << FP64_MANT) | (kept & MMASK_52)

    # binary64 subnormal / underflow region (E2 <= -1023).
    # value = full_sig * 2^(E2 - M); as integer units of 2^-1074:
    #   units = full_sig * 2^((E2-M) + 1074); shift right by sh = -(E2-M+1074).
    sh = -(E2 - M + 1074)                        # = -E2 + M - 1074 = -E2 - 1015
    # sh in [8 .. very large]. If sh >= sigbits+1 (>=61) -> definitely 0 (no
    # bit reaches the guard position). If sh == sigbits (==60) the top bit is
    # exactly the guard (can round up to 1). Only sh <= 60 needs real work,
    # and crucially we must NOT materialize 1<<(sh-1) for huge sh.
    if sh > sigbits:                             # sh >= 61 -> underflow to 0
        return s << 63
    # sh in [8 .. 60]
    mant = full_sig >> sh
    dropped = full_sig - (mant << sh)
    half = 1 << (sh - 1)
    if dropped > half or (dropped == half and (mant & 1)):
        mant += 1
    if mant == 0:
        return s << 63
    if mant >= (1 << FP64_MANT):                 # carried into smallest normal
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
        # specials
        codes.add(base)                                  # +-0
        codes.add(base | (EMAX << M))                    # +-inf
        codes.add(base | (EMAX << M) | 1)                # nan (payload 1)
        codes.add(base | (EMAX << M) | MMAX)             # nan (payload all-ones)
        # gf96 subnormals (e==0) -- all flush to binary64 +-0, but exercise the
        # renormalise datapath + the underflow branch.
        for mv in (1, MMAX, MMAX // 2, 1 << (M - 1), (1 << (M - 1)) - 1, 3, 0x7FF):
            codes.add(base | mv)

    # ---- the only region where FINITE nonzero binary64 is produced: e ~= BIAS.
    # Binary64 boundaries in gf96-exponent units (true_exp = e - BIAS):
    #   overflow->inf  : true_exp >= 1024          -> e >= BIAS+1024
    #   normal max     : true_exp == 1023          -> e == BIAS+1023
    #   normal/subnorm : true_exp == -1022         -> e == BIAS-1022
    #   subnormal min  : true_exp == -1074         -> e == BIAS-1074
    #   underflow->0   : true_exp <= -1075         -> e <= BIAS-1075
    exp_samples = set()
    # dense window covering normal + subnormal + a margin either side
    for de in range(-1130, 1075):
        ce = BIAS + de
        if 1 <= ce < EMAX:
            exp_samples.add(ce)
    # exact boundary exponents (the class transitions)
    for boundary in (1024, 1023, 1022, -1022, -1023, -1074, -1075, -1076):
        ce = BIAS + boundary
        if 1 <= ce < EMAX:
            exp_samples.add(ce)
    # representative mantissas: stress the low 7 bits (the rounded-away bits)
    mant_reps = [
        0, MMAX, MMAX // 2,
        1, 1 << (M - 1), (1 << (M - 1)) - 1,
        # exact-half / guard / sticky patterns in the low 7 bits:
        MMAX - 1, 0x7F, 0x40, 0x3F, 0x7F << 1, (MMASK >> 7) << 7, (MMASK >> 7) << 7 | 0x3F,
    ]
    for s in (0, 1):
        base = s << (N - 1)
        for e in sorted(exp_samples):
            for mv in mant_reps:
                codes.add(base | (e << M) | mv)

    # far field: exponents far from BIAS -> exercise inf / 0 classes
    far = set()
    for e in (1, 2, 3, 100, 1000, 1 << 17, 1 << 20, EMAX - 1, EMAX - 2,
              BIAS - (1 << 20), BIAS - (1 << 17), BIAS - 1000, BIAS - 100):
        if 1 <= e < EMAX:
            far.add(e)
    for s in (0, 1):
        base = s << (N - 1)
        for e in sorted(far):
            for mv in (0, MMAX, MMAX // 2, 1, 0x7F):
                codes.add(base | (e << M) | mv)

    # deterministic random fill (seed stable for reproducibility)
    import random
    rng = random.Random(20260724)
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
                s, e, m = gf96_fields(raw)
                print(f"  A!=B raw={raw:#026x} (s={s} e={e} m={m:#018x}) "
                      f"A={a:#018x} B={b:#018x}", file=sys.stderr)
            mism_ab += 1
        dump.append((raw, a))
    print(f"WITNESS CROSS-CHECK (A mpmath-exact vs B integer-construct): "
          f"{len(codes)-mism_ab}/{len(codes)} agree (mismatch={mism_ab})")
    import os
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gf96_vectors.hex")
    with open(out_path, "w") as f:
        for raw, exp in dump:
            f.write(f"{raw:024x} {exp:016x}\n")     # 96-bit raw = 24 nybbles
    print(f"Wrote {len(dump)} vectors to gf96_vectors.hex")
    return 0 if mism_ab == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
