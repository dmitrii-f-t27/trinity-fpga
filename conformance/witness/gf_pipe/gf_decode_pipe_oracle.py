#!/usr/bin/env python3
"""Golden Fraction oracle for gf{N} -> FP32 decode (independent of the RTL).

Emits iverilog test vectors: one line "GFHEX FP32HEX" per case. The RTL
testbench (tb_gf_decode_param_pipe.v) reads these and compares bit-for-bit
against gf_decode_param_pipe.v (latency=2). This oracle is a SECOND,
structurally independent decode path (exact rational -> RNE to binary32),
NOT a transcription of the Verilog -- satisfies the 2-witness honesty rule.

Trinity Catalog-100 horizon-B routing prep, 2026-07-24.
Author: Vasilev (gHashTag), ORCID 0009-0008-4294-6159.
Status: [verified SW на iverilog] once the tb passes.
"""
import sys, struct, argparse
from fractions import Fraction


def pow2(e):
    """Exact Fraction 2^e for any integer e."""
    return Fraction(1 << e) if e >= 0 else Fraction(1, 1 << (-e))


def fp32_bits_from_fraction(sign, frac):
    """Round an exact non-negative Fraction to IEEE binary32, RNE. Return u32."""
    if frac == 0:
        return (sign << 31)
    # Find integer e with 2^e <= frac < 2^(e+1) using exact rational compare.
    num, den = frac.numerator, frac.denominator
    e = num.bit_length() - den.bit_length()      # within +/-1 of the true value
    while frac < pow2(e):
        e -= 1
    while frac >= pow2(e + 1):
        e += 1

    if e >= -126:
        # normal candidate: mantissa = frac/2^e in [1,2), scaled by 2^23
        mant_scaled = (frac / pow2(e)) * (1 << 23)   # in [2^23, 2^24)
        q = round_half_even(mant_scaled)
        if q == (1 << 24):                            # rounded up to 2.0
            q = 1 << 23
            e += 1
        if e > 127:
            return (sign << 31) | 0x7F800000          # overflow -> inf
        mant = q - (1 << 23)
        biased = e + 127
        return (sign << 31) | (biased << 23) | mant
    else:
        # subnormal (or underflow): value in units of 2^-149
        units = frac / pow2(-149)
        q = round_half_even(units)
        if q >= (1 << 23):                            # rounded up to smallest normal
            return (sign << 31) | (1 << 23)
        return (sign << 31) | q


def round_half_even(fr):
    """Round a Fraction to nearest integer, ties to even."""
    fl = fr.numerator // fr.denominator
    rem = fr - fl
    if rem < Fraction(1, 2):
        return fl
    if rem > Fraction(1, 2):
        return fl + 1
    return fl if (fl % 2 == 0) else fl + 1


def gf_decode_exact(word, N, E, M, BIAS):
    """Independent exact decode: return ('nan'|'inf'|('val',sign,Fraction))."""
    sign = (word >> (N - 1)) & 1
    exp = (word >> M) & ((1 << E) - 1)
    mant = word & ((1 << M) - 1)
    exp_max = (1 << E) - 1
    if exp == exp_max and mant == 0:
        return ('inf', sign, None)
    if exp == exp_max and mant != 0:
        return ('nan', sign, None)
    if exp == 0 and mant == 0:
        return ('val', sign, Fraction(0))
    if exp == 0:  # subnormal
        val = Fraction(mant, 1 << M) * (Fraction(2) ** (1 - BIAS))
        return ('val', sign, val)
    # normal
    val = (Fraction(1) + Fraction(mant, 1 << M)) * (Fraction(2) ** (exp - BIAS))
    return ('val', sign, val)


def expected_fp32(word, N, E, M, BIAS):
    kind, sign, val = gf_decode_exact(word, N, E, M, BIAS)
    if kind == 'nan':
        return 0x7FC00001
    if kind == 'inf':
        return (sign << 31) | 0x7F800000
    return fp32_bits_from_fraction(sign, val)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--N", type=int, required=True)
    ap.add_argument("--E", type=int, required=True)
    ap.add_argument("--M", type=int, required=True)
    ap.add_argument("--BIAS", type=int, required=True)
    ap.add_argument("--mode", choices=["exhaustive", "representative"], default="representative")
    ap.add_argument("--seed", type=int, default=20260724)
    ap.add_argument("--count", type=int, default=20000)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    words = []
    total = 1 << a.N
    if a.mode == "exhaustive" or total <= a.count:
        words = list(range(total))
    else:
        import random
        r = random.Random(a.seed)
        s = set()
        # always include the 5-class corners + all-exp boundaries
        for exp in [0, 1, (1 << a.E) - 2, (1 << a.E) - 1]:
            for mant in [0, 1, (1 << a.M) - 1, (1 << a.M) >> 1]:
                for sgn in [0, 1]:
                    s.add((sgn << (a.N - 1)) | (exp << a.M) | (mant & ((1 << a.M) - 1)))
        while len(s) < a.count:
            s.add(r.getrandbits(a.N))
        words = sorted(s)

    with open(a.out, "w") as f:
        for w in words:
            fp = expected_fp32(w, a.N, a.E, a.M, a.BIAS)
            f.write(f"{w:0{(a.N + 3) // 4}x} {fp:08x}\n")
    print(f"wrote {len(words)} vectors to {a.out} (N={a.N} E={a.E} M={a.M} BIAS={a.BIAS})")


if __name__ == "__main__":
    main()
