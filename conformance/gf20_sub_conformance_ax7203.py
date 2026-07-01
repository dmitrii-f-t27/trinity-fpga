#!/usr/bin/env python3
# gf20_sub_conformance_ax7203.py — GF20 SUB compute-conformance on AX7203.
# SUB(a,b) = ADD(a,-b). Flashed design (fpga/vivado/gf20_sub_ax7203.v) flips b's
# sign bit (bit 19) then runs gf_adder_param #(7,12) — silicon-PROVEN for ADD
# (480/480). Golden = gf_ref.gf_add(GF20, a, b ^ 0x80000). Wider 9-byte/4-byte frame.
#
#   self-test:   python3 gf20_sub_conformance_ax7203.py --self-test
#   on hardware: python3 gf20_sub_conformance_ax7203.py --port /dev/cu.usbserial-120 --baud 160000
import argparse, sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gf_ref import FORMATS, gf_add

GFMT = FORMATS["gf20"]         # 1S+7E+12M, bias=63, HAS_INF=0
SIGN = 1 << (GFMT.exp_bits + GFMT.mant_bits)   # sign bit = 0x80000 for GF20
T = 1 << (GFMT.exp_bits + GFMT.mant_bits + 1)  # 2^20


def golden_sub(a, b):
    return gf_add(GFMT, a, b ^ SIGN)


FRAME = bytes([0xAA, 0x55])


def hw_exchange(ser, a, b):
    # 9-byte frame: AA 55 a_lo a_mid a_hi(nib) b_lo b_mid b_hi(nib) trig
    pkt = FRAME + bytes([a & 0xFF, (a >> 8) & 0xFF, (a >> 16) & 0xF,
                         b & 0xFF, (b >> 8) & 0xFF, (b >> 16) & 0xF, 0x00])
    ser.write(pkt)
    resp = ser.read(4)
    if len(resp) != 4 or resp[0] != 0xA5:
        return None
    return resp[1] | (resp[2] << 8) | (resp[3] << 16)   # 20-bit result


def self_test():
    # GF20 has no Inf/NaN -> a-0=a holds for ALL inputs (x + (-0) = x).
    rnd = random.Random(42)
    corners = [0x00000, 0x00001, 0xFFFFF, SIGN, 0x40000, 0x80001, 0x30000]
    bad = 0
    for a in corners:
        for b in corners:
            _ = golden_sub(a, b)            # corner no-crash
    for _ in range(3000):                   # a - 0 == a (core identity)
        a = rnd.randint(0, T - 1)
        if golden_sub(a, 0) != a:
            bad += 1
    spot = golden_sub(0x40000, 0x40000)     # finite a: a - a -> +0
    print(f"self-test: a-0==a over 3000 random + corner no-crash, {bad} failures; "
          f"gf20_sub(0x40000,0x40000)=0x{spot:05x} (expect 0x00000)")
    return bad == 0 and spot == 0


def run_hw(port, baud, n, exhaustive=False):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0; checked = 0
    rnd = random.Random(42)
    corners = [0x00000, 0x00001, 0xFFFFF, SIGN, 0x40000, 0x80001, 0x30000, 0x78000]
    sample = corners + [rnd.randint(0, T - 1) for _ in range(max(0, n - len(corners)))]
    for a in sample:
        for b in sample[:8]:
            hw = hw_exchange(ser, a, b)
            gold = golden_sub(a, b)
            checked += 1
            if hw is None or hw != gold:
                fails += 1
                if fails <= 10:
                    print(f"MISMATCH a=0x{a:05x} b=0x{b:05x} hw={hw} gold=0x{gold:05x}")
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
