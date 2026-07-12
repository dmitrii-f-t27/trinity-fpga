#!/usr/bin/env python3
"""compute_conformance_template.py — generalized compute-host for AX7203.
Tests ADD, MUL, DIV, SQRT, QUIRE for any format that has a compute bitstream.

Usage:
  python3 compute_conformance_template.py --port /dev/cu.usbserial-1120 --fmt gf16 --op add
  python3 compute_conformance_template.py --port /dev/cu.usbserial-1120 --fmt gf8 --op mul
  python3 compute_conformance_template.py --port /dev/cu.usbserial-1120 --fmt gf16 --op div
  python3 compute_conformance_template.py --port /dev/cu.usbserial-1120 --fmt gf16 --op sqrt
  python3 compute_conformance_template.py --port /dev/cu.usbserial-1120 --fmt gf16 --op quire

Supports: gf4, gf6, gf8, gf10, gf12, gf14, gf16, gf20, gf24, gf32, bf16
Operations: add, mul, div, sqrt, quire
"""
import argparse, sys, struct, random

# Format definitions: (total_bits, nbytes, exponent_bits, mantissa_bits, bias)
FORMATS = {
    "gf4":  (4,  1, 2, 2, 1),
    "gf6":  (6,  1, 2, 3, 1),
    "gf8":  (8,  1, 3, 4, 3),
    "gf10": (10, 2, 3, 6, 3),
    "gf12": (12, 2, 3, 8, 3),
    "gf14": (14, 2, 4, 9, 7),
    "gf16": (16, 2, 5, 10, 15),
    "gf20": (20, 3, 6, 13, 31),
    "gf24": (24, 3, 6, 17, 31),
    "gf32": (32, 4, 7, 25, 63),
    "bf16": (16, 2, 8, 7, 127),
}

FRAME = bytes([0xAA, 0x55])

def golden_fp32(a_bits, b_bits, fmt_name, op):
    """Compute golden result using Python struct fp32 arithmetic."""
    total, nbytes, E, M, BIAS = FORMATS[fmt_name]
    sign_bit = total - 1
    exp_lo = M
    exp_hi = M + E - 1
    e_max = (1 << E) - 1

    def to_fp32(val):
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
            # subnormal
            de = 1 - BIAS + 127
            if M > 0:
                mant_norm = 0
                m = mant
                while m > 0 and m < (1 << (M-1)):
                    m <<= 1
                    de -= 1
                fp32_exp = max(0, min(254, de + 127))
                fp32_mant = (m & ((1 << min(M,23)) - 1)) << max(0, 23 - M)
            else:
                fp32_exp = max(0, de)
                fp32_mant = 0
        else:
            de = exp - BIAS + 127
            fp32_exp = max(0, min(254, de))
            fp32_mant = (mant << max(0, 23 - M)) if M > 0 else 0
        fp32_bits = (s << 31) | (fp32_exp << 23) | (fp32_mant & 0x7FFFFF)
        return struct.unpack('<f', struct.pack('<I', fp32_bits))[0]

    def from_fp32(f):
        if f != f:
            return 0  # NaN -> 0 for simplicity
        if f == 0.0:
            return 0
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

    a = to_fp32(a_bits)
    b = to_fp32(b_bits)
    if op == "add":
        result = a + b
    elif op == "mul":
        result = a * b
    elif op == "div":
        if b == 0.0:
            return (1 << sign_bit) | (e_max << exp_lo)  # Inf
        result = a / b
    elif op == "sqrt":
        import math
        if a < 0:
            return 0  # NaN -> 0
        result = math.sqrt(a)
    elif op == "quire":
        # Quire: accumulate a into running sum, b selects op (0=add)
        # For golden: just return a (single accumulate test)
        result = a
    else:
        raise ValueError(f"Unknown op: {op}")
    return from_fp32(result)


def hw_exchange(ser, a, b, nbytes):
    """Send a,b to FPGA and read back result."""
    pkt = FRAME
    for i in range(nbytes):
        pkt += bytes([(a >> (8*i)) & 0xFF])
    for i in range(nbytes):
        pkt += bytes([(b >> (8*i)) & 0xFF])
    pkt += bytes([0x00])  # trigger
    ser.write(pkt)
    resp_size = nbytes + 1  # A5 + nbytes data
    resp = ser.read(resp_size)
    if len(resp) < 1 or resp[0] != 0xA5:
        return None
    result = 0
    for i in range(1, min(nbytes+1, len(resp))):
        result |= resp[i] << (8*(i-1))
    return result


def run_hw(port, baud, fmt_name, op, n):
    import serial
    total, nbytes, E, M, BIAS = FORMATS[fmt_name]
    T = 1 << total
    ser = serial.Serial(port, baud, timeout=3)
    fails = 0; checked = 0
    rnd = random.Random(42)
    corners = [0, 1, T-1, 1 << (total-1), T//2, T//4]
    sample = corners + [rnd.randint(0, T-1) for _ in range(max(0, n - len(corners)))]
    for a in sample:
        for b in sample[:min(8, len(sample))]:
            hw = hw_exchange(ser, a, b, nbytes)
            gold = golden_fp32(a, b, fmt_name, op)
            checked += 1
            if hw is None or hw != gold:
                fails += 1
                if fails <= 5:
                    print(f"MISMATCH a=0x{a:0{nbytes*2}x} b=0x{b:0{nbytes*2}x} hw={hw} gold=0x{gold:0{nbytes*2}x}")
    ser.close()
    print(f"HW RESULT: {checked - fails}/{checked} bit-exact (fails={fails})")
    return fails == 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generalized compute conformance for AX7203")
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--fmt", required=True, choices=list(FORMATS.keys()))
    ap.add_argument("--op", required=True, choices=["add", "mul", "div", "sqrt", "quire"])
    ap.add_argument("--n", type=int, default=64)
    args = ap.parse_args()
    sys.exit(0 if run_hw(args.port, args.baud, args.fmt, args.op, args.n) else 1)
