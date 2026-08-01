#!/usr/bin/env python3
# gf32_mul_conformance_ax7203.py — GF32 MUL compute-conformance on AX7203.
# MUL(a,b) via gf_mul_param #(12,19), no flip. Golden = gf_ref.gf_mul(GF32, a, b).
# Wider 11-byte/5-byte frame (same as gf32_sub/gf32_add).
import argparse, sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gf_ref import FORMATS, gf_mul

GFMT = FORMATS["gf32"]         # 1S+12E+19M, bias=2047, HAS_INF=0
SIGN = 1 << (GFMT.exp_bits + GFMT.mant_bits)   # 0x80000000
T = 1 << (GFMT.exp_bits + GFMT.mant_bits + 1)  # 2^32
ONE = GFMT.bias << GFMT.mant_bits              # GF32 1.0 = exp=bias(2047), mant=0 = 0x3FF80000


def golden_mul(a, b):
    return gf_mul(GFMT, a, b)


FRAME = bytes([0xAA, 0x55])  # magic only — the gf compute wrappers have no fmt byte


def hw_exchange(ser, a, b):
    pkt = FRAME + bytes([a & 0xFF, (a >> 8) & 0xFF, (a >> 16) & 0xFF, (a >> 24) & 0xFF,
                         b & 0xFF, (b >> 8) & 0xFF, (b >> 16) & 0xFF, (b >> 24) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return resp[1] | (resp[2] << 8) | (resp[3] << 16) | (resp[4] << 24)


def self_test():
    # a*1==a holds for ALL finite GF32 inputs (no Inf/NaN).
    rnd = random.Random(42)
    corners = [0x00000000, 0x00000001, 0xFFFFFFFF, SIGN, 0x40000000, 0x80000001, 0x30000000]
    bad = 0
    for a in corners:
        for b in corners:
            _ = golden_mul(a, b)
    for _ in range(3000):
        a = rnd.randint(0, T - 1)
        if golden_mul(a, ONE) != a:
            bad += 1
    spot = golden_mul(0x40000000, ONE)          # 2.0 * 1.0 -> 2.0
    print(f"self-test: a*1==a over 3000 random + corner no-crash, {bad} failures; "
          f"gf32_mul(0x40000000,0x{ONE:08x})=0x{spot:08x} (expect 0x40000000)")
    return bad == 0 and spot == 0x40000000


def run_hw(port, baud, n):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0; checked = 0
    rnd = random.Random(42)
    corners = [0x00000000, 0x00000001, 0xFFFFFFFF, SIGN, 0x40000000, 0x80000001, 0x30000000, ONE]
    sample = corners + [rnd.randint(0, T - 1) for _ in range(max(0, n - len(corners)))]
    for a in sample:
        for b in sample[:8]:
            hw = hw_exchange(ser, a, b)
            gold = golden_mul(a, b)
            checked += 1
            if hw is None or hw != gold:
                fails += 1
                if fails <= 10:
                    print(f"MISMATCH a=0x{a:08x} b=0x{b:08x} hw={hw} gold=0x{gold:08x}")
    ser.close()
    print(f"HW RESULT: {checked - fails}/{checked} bit-exact (fails={fails})")
    return fails == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=64)
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    sys.exit(0 if run_hw(a.port, a.baud, a.n) else 1)


if __name__ == "__main__":
    main()
