#!/usr/bin/env python3
# gf32_sub_conformance_ax7203.py — GF32 SUB compute-conformance on AX7203.
# SUB(a,b) = ADD(a,-b). Flashed design (fpga/vivado/gf32_sub_ax7203.v) flips b's
# sign bit (bit 31) then runs gf_adder_param #(12,19). Golden =
# gf_ref.gf_add(GF32, a, b ^ 0x80000000). Wider 11-byte/5-byte frame.
#
#   self-test:   python3 gf32_sub_conformance_ax7203.py --self-test
#   on hardware: python3 gf32_sub_conformance_ax7203.py --port /dev/cu.usbserial-120 --baud 160000
import argparse, sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gf_ref import FORMATS, gf_add

GFMT = FORMATS["gf32"]         # 1S+12E+19M, bias=2047, HAS_INF=0
SIGN = 1 << (GFMT.exp_bits + GFMT.mant_bits)   # sign bit = 0x80000000 for GF32
T = 1 << (GFMT.exp_bits + GFMT.mant_bits + 1)  # 2^32


def golden_sub(a, b):
    return gf_add(GFMT, a, b ^ SIGN)


FRAME = bytes([0xAA, 0x55])


def hw_exchange(ser, a, b):
    # 11-byte frame: AA 55 a_lo a_mlo a_mhi a_hi b_lo b_mlo b_mhi b_hi trig
    pkt = FRAME + bytes([a & 0xFF, (a >> 8) & 0xFF, (a >> 16) & 0xFF, (a >> 24) & 0xFF,
                         b & 0xFF, (b >> 8) & 0xFF, (b >> 16) & 0xFF, (b >> 24) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return resp[1] | (resp[2] << 8) | (resp[3] << 16) | (resp[4] << 24)   # 32-bit result


def self_test():
    # GF32 has no Inf/NaN -> a-0=a holds for ALL inputs (x + (-0) = x).
    rnd = random.Random(42)
    corners = [0x00000000, 0x00000001, 0xFFFFFFFF, SIGN, 0x40000000, 0x80000001, 0x30000000]
    bad = 0
    for a in corners:
        for b in corners:
            _ = golden_sub(a, b)            # corner no-crash
    for _ in range(3000):                   # a - 0 == a (core identity)
        a = rnd.randint(0, T - 1)
        if golden_sub(a, 0) != a:
            bad += 1
    spot = golden_sub(0x40000000, 0x40000000)   # 2.0 - 2.0 -> +0
    print(f"self-test: a-0==a over 3000 random + corner no-crash, {bad} failures; "
          f"gf32_sub(0x40000000,0x40000000)=0x{spot:08x} (expect 0x00000000)")
    return bad == 0 and spot == 0


def run_hw(port, baud, n):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0; checked = 0
    rnd = random.Random(42)
    corners = [0x00000000, 0x00000001, 0xFFFFFFFF, SIGN, 0x40000000, 0x80000001, 0x30000000, 0x7FF80000]
    sample = corners + [rnd.randint(0, T - 1) for _ in range(max(0, n - len(corners)))]
    for a in sample:
        for b in sample[:8]:
            hw = hw_exchange(ser, a, b)
            gold = golden_sub(a, b)
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
    ap.add_argument("--port", default="/dev/cu.usbserial-120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=64)
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    sys.exit(0 if run_hw(a.port, a.baud, a.n) else 1)


if __name__ == "__main__":
    main()
