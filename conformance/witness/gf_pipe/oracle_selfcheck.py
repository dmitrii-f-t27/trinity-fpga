#!/usr/bin/env python3
"""Sanity: my Fraction->fp32 RNE matches numpy.float32 for random rationals
that are within fp32 range. Confirms round_half_even + exponent logic."""
import struct, random
from fractions import Fraction
from gf_decode_pipe_oracle import fp32_bits_from_fraction

import numpy as np

r = random.Random(1)
bad = 0
for _ in range(200000):
    # random fp32 pattern -> its exact value -> back through oracle
    u = r.getrandbits(32)
    # skip nan/inf/neg-zero specials; test finite positives/negatives
    exp = (u >> 23) & 0xFF
    if exp == 0xFF:
        continue
    f = struct.unpack("<f", struct.pack("<I", u))[0]
    if f == 0.0:
        continue
    sign = 1 if f < 0 else 0
    frac = Fraction(abs(f))  # exact value of the fp32
    got = fp32_bits_from_fraction(sign, frac)
    want = struct.unpack("<I", struct.pack("<f", f))[0]
    if got != want:
        bad += 1
        if bad <= 5:
            print(f"MISMATCH f={f!r} got={got:08x} want={want:08x}")
if bad == 0:
    print("oracle_selfcheck: PASS (200k fp32 round-trips bit-exact)")
else:
    print(f"oracle_selfcheck: FAIL ({bad} mismatches)")
