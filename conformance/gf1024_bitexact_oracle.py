#!/usr/bin/env python3
"""gf1024 STRICT bit-exact oracle -- GF(1024, E=391, M=632, BIAS=2^390-1) -> binary64.

Final format of the strict SW-bitexact line (horizon-A closure). M=632 ->
632-52 = 580 mantissa bits rounded RNE per normal decode. BIAS = 2^390-1.

Three independent witnesses (A==B==C over representative+boundary+random sweep):
  (A) exact mpmath mpf (dps=700 >> 632 bits) -> binary64 via frexp+scaling+RNE.
  (B) pure integer field-construct, guard/sticky for 632->52.
  (C) RTL gf1024_decode_fp64.v via iverilog.

THEORETICAL-ONLY (GF1024 ~1605% of XC7A200T): decode is provably bit-exact but
can NEVER be Tier-E (exceeds any current FPGA by ~16x).

Author: Vasilev (gHashTag), ORCID 0009-0008-4294-6159, admin@t27.ai.
"""
import mpmath
import os
import sys

mpmath.mp.dps = 700   # >> 632 mantissa bits -> every dyadic input value is exact

N, E, M, BIAS = 1024, 391, 632, (1 << 390) - 1     # BIAS = 2^390 - 1
EMASK = (1 << E) - 1
MMASK = (1 << M) - 1
EMAX = EMASK

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


def gf1024_fields(raw):
    raw &= (1 << N) - 1
    s = raw >> (N - 1)
    e = (raw >> M) & EMASK
    m = raw & MMASK
    return s, e, m


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
    s, e, m = gf1024_fields(raw)
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


def witness_B(raw):
    s, e, m = gf1024_fields(raw)
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
    sigbits = M + 1                                 # 633
    E2 = true_exp

    if E2 >= FP64_MAX_EXP:
        return NEG_INF64 if s else POS_INF64

    if E2 >= FP64_MIN_NORM_EXP:
        drop = sigbits - 53                         # 580 for gf1024
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

    sh = -(E2 - M + 1074)                           # = -E2 + M - 1074
    if sh > sigbits:                                # sh >= 634 -> underflow to 0
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


def sample_codes():
    codes = set()
    MMAX = MMASK
    for s in (0, 1):
        base = s << (N - 1)
        codes.add(base)
        codes.add(base | (EMAX << M))
        codes.add(base | (EMAX << M) | 1)
        codes.add(base | (EMAX << M) | MMAX)
        for mv in (1, MMAX, MMAX // 2, 1 << (M - 1), (1 << (M - 1)) - 1, 3, 0x7F):
            codes.add(base | mv)

    exp_samples = set()
    for de in range(-1130, 1075):
        ce = BIAS + de
        if 1 <= ce < EMAX:
            exp_samples.add(ce)
    for boundary in (1024, 1023, 1022, -1022, -1023, -1074, -1075, -1076):
        ce = BIAS + boundary
        if 1 <= ce < EMAX:
            exp_samples.add(ce)
    mant_reps = [0, MMAX, MMAX // 2, 1, 1 << (M - 1), (1 << (M - 1)) - 1, MMAX - 1]
    for s in (0, 1):
        base = s << (N - 1)
        for e in sorted(exp_samples):
            for mv in mant_reps:
                codes.add(base | (e << M) | mv)

    import random
    rng = random.Random(20260731)
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
                print(f"  A!=B raw={raw:#0258x} A={a:#018x} B={b:#018x}", file=sys.stderr)
            mism_ab += 1
        dump.append((raw, a))
    print(f"WITNESS CROSS-CHECK (A mpmath-exact vs B integer-construct): "
          f"{len(codes)-mism_ab}/{len(codes)} agree (mismatch={mism_ab})")
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gf1024_vectors.hex")
    with open(out_path, "w") as f:
        for raw, exp in dump:
            f.write(f"{raw:0256x} {exp:016x}\n")    # 1024-bit raw = 256 nybbles
    print(f"Wrote {len(dump)} vectors to gf1024_vectors.hex")
    return 0 if mism_ab == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
