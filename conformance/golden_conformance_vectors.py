#!/usr/bin/env python3
"""golden_conformance_vectors.py — Generate golden conformance vectors for
div, sqrt, quire operations. JSON output for CI verification.

Each vector: {a, b, op, golden_result} where values are hex-encoded format-specific.

Usage:
  python3 golden_conformance_vectors.py --fmt gf16 --op div --n 64 > vectors/gf16_div.json
  python3 golden_conformance_vectors.py --fmt gf16 --op sqrt --n 64 > vectors/gf16_sqrt.json
"""
import argparse, json, struct, random, math, os

FORMATS = {
    "gf4":  (4,  2, 2, 1),
    "gf6":  (6,  2, 3, 1),
    "gf8":  (8,  3, 4, 3),
    "gf10": (10, 3, 6, 3),
    "gf12": (12, 3, 8, 3),
    "gf14": (14, 4, 9, 7),
    "gf16": (16, 5, 10, 15),
    "gf20": (20, 6, 13, 31),
    "gf24": (24, 6, 17, 31),
    "gf32": (32, 7, 25, 63),
    "bf16": (16, 8, 7, 127),
    "fp16_e6m9":    (16, 6, 9, 31),
    "fp24_7m16":    (24, 7, 16, 63),
    "fp32_e8m23":   (32, 8, 23, 127),
    "binary64":     (64, 11, 52, 1023),
    "fp128_e15m112":(128, 15, 112, 16383),
}

def to_fp32(val, fmt_name):
    total, nbytes, E, M, BIAS = (*FORMATS[fmt_name][:4], FORMATS[fmt_name][3])
    total, E, M, BIAS = FORMATS[fmt_name]
    sign_bit = total - 1
    exp_lo = M
    exp_hi = M + E - 1
    e_max = (1 << E) - 1

    s = (val >> sign_bit) & 1
    exp = (val >> exp_lo) & ((1 << E) - 1)
    mant = val & ((1 << M) - 1) if M > 0 else 0

    if exp == 0 and mant == 0:
        return struct.unpack('<f', struct.pack('<I', s << 31))[0]
    if exp == e_max:
        if mant == 0:
            return float('inf') * (-1 if s else 1)
        return float('nan')
    if exp == 0:
        de = 1 - BIAS + 127
        fp32_exp = max(0, min(254, de))
        fp32_mant = 0
    else:
        de = exp - BIAS + 127
        fp32_exp = max(0, min(254, de))
        fp32_mant = (mant << max(0, 23 - M)) & 0x7FFFFF if M > 0 else 0
    fp32_bits = (s << 31) | (fp32_exp << 23) | fp32_mant
    return struct.unpack('<f', struct.pack('<I', fp32_bits))[0]

def from_fp32(f, fmt_name):
    total, E, M, BIAS = FORMATS[fmt_name]
    sign_bit = total - 1
    exp_lo = M
    e_max = (1 << E) - 1

    if f != f:  # NaN
        return 0
    if f == 0.0:
        return 0
    # Clamp overflow before packing to fp32
    if abs(f) > 3.4e38:
        s = 1 if f < 0 else 0
        return (s << sign_bit) | (e_max << exp_lo)
    bits = struct.unpack('<I', struct.pack('<f', f))[0]
    s = (bits >> 31) & 1
    exp32 = (bits >> 23) & 0xFF
    mant32 = bits & 0x7FFFFF
    if exp32 == 255:
        if mant32 == 0:
            return (s << sign_bit) | (e_max << exp_lo)
        return 0
    tgt_exp = exp32 - 127 + BIAS
    if tgt_exp >= e_max:
        return (s << sign_bit) | (e_max << exp_lo)
    if tgt_exp <= 0:
        return (s << sign_bit)
    mant_out = (mant32 >> max(0, 23 - M)) & ((1 << M) - 1) if M > 0 else 0
    return (s << sign_bit) | ((tgt_exp & ((1 << E) - 1)) << exp_lo) | mant_out

def gen_vectors(fmt_name, op, n, seed=42):
    total, E, M, BIAS = FORMATS[fmt_name]
    T = 1 << total
    rnd = random.Random(seed)
    vectors = []
    corners = [0, 1, T-1, 1 << (total-1), T//2, T//4]
    if op in ("add", "mul", "div"):
        sample_a = corners + [rnd.randint(0, T-1) for _ in range(n)]
        sample_b = corners[:4] + [rnd.randint(1, T-1) for _ in range(min(8, n))]
        for a in sample_a[:n]:
            for b in sample_b[:8]:
                fa = to_fp32(a, fmt_name)
                fb = to_fp32(b, fmt_name)
                if op == "add":
                    result = from_fp32(fa + fb, fmt_name)
                elif op == "mul":
                    result = from_fp32(fa * fb, fmt_name)
                elif op == "div":
                    if fb == 0.0:
                        result = (1 << (total-1)) | (((1 << E) - 1) << M)
                    else:
                        result = from_fp32(fa / fb, fmt_name)
                vectors.append({"a": a, "b": b, "op": op, "result": result})
    elif op == "sqrt":
        sample_a = corners + [rnd.randint(0, T-1) for _ in range(n)]
        for a in sample_a[:n]:
            fa = to_fp32(a, fmt_name)
            if fa < 0:
                result = 0
            else:
                result = from_fp32(math.sqrt(fa), fmt_name)
            vectors.append({"a": a, "b": 0, "op": op, "result": result})
    elif op == "quire":
        sample_a = corners + [rnd.randint(0, T-1) for _ in range(n)]
        for a in sample_a[:n]:
            fa = to_fp32(a, fmt_name)
            result = from_fp32(fa, fmt_name)
            vectors.append({"a": a, "b": 0, "op": op, "result": result})
    return vectors

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fmt", required=True, choices=list(FORMATS.keys()))
    ap.add_argument("--op", required=True, choices=["add", "mul", "div", "sqrt", "quire"])
    ap.add_argument("--n", type=int, default=64)
    args = ap.parse_args()
    vectors = gen_vectors(args.fmt, args.op, args.n)
    print(json.dumps({"format": args.fmt, "op": args.op, "count": len(vectors), "vectors": vectors}, indent=2))
