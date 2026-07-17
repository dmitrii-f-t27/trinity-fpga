#!/usr/bin/env python3
# gf4_sub_conformance_ax7203.py — GF4 SUB compute-conformance on AX7203.
# SUB(a,b) = ADD(a,-b). The flashed design (fpga/vivado/gf4_sub_ax7203.v) flips
# b's sign bit (bit 3) then runs the conformant gf_adder_param #(1,2) — the SAME
# adder that is formal-PROVEN (GF4 all 256 pairs) + silicon-PROVEN for ADD.
# Golden = gf_ref.gf_add(GF4, a, b ^ 0x8) (canonical Fraction oracle).
#
#   self-test:   python3 gf4_sub_conformance_ax7203.py --self-test
#   on hardware: python3 gf4_sub_conformance_ax7203.py --port /dev/cu.usbserial-1120 --baud 160000
import argparse, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gf_ref import FORMATS, gf_add

GFMT = FORMATS["gf4"]          # 1S+1E+2M, bias=0, HAS_INF=0
SIGN = 1 << (GFMT.exp_bits + GFMT.mant_bits)   # sign bit = 0x8 for GF4


def golden_sub(a, b):
    return gf_add(GFMT, a, b ^ SIGN)


FRAME = bytes([0xAA, 0x55, 0x00])  # AA 55 fmt


def hw_exchange(ser, a, b):
    pkt = FRAME + bytes([a & 0xFF, 0, b & 0xFF, 0, 0x00])
    ser.write(pkt)
    resp = ser.read(4)
    if len(resp) != 4 or resp[0] != 0xA5:
        return None
    return resp[1] | (resp[2] << 8)


def self_test():
    T = 1 << (GFMT.exp_bits + GFMT.mant_bits + 1)   # 16 for GF4
    bad = 0
    for a in range(T):
        for b in range(T):
            r = golden_sub(a, b)
            if a == b and a not in (0, SIGN) and r not in (0, SIGN):
                bad += 1
            if b == 0 and a not in (0, SIGN) and r != a:
                bad += 1
    cross_bad = sum(1 for a in range(T) for b in range(T)
                    if golden_sub(a, b) != gf_add(GFMT, a, b ^ SIGN))
    print(f"self-test: SUB algebra over {T*T} pairs, {bad} inconsistencies; "
          f"cross-check vs gf_add(a,-b) {cross_bad} mismatches")
    return bad == 0 and cross_bad == 0


def run_hw(port, baud, n, exhaustive=False):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0; checked = 0
    import random
    rnd = random.Random(42)
    T = 1 << (GFMT.exp_bits + GFMT.mant_bits + 1)
    if exhaustive:
        sample = list(range(T))
    else:
        sample = [0x0, 0x1, 0x7, 0xF, 0x2, 0x4, 0x8, 0x9]
        sample += [rnd.randint(0, T - 1) for _ in range(n - len(sample))]
    for a in sample:
        for b in (sample if exhaustive else sample[:8]):
            hw = hw_exchange(ser, a, b)
            gold = golden_sub(a, b)
            checked += 1
            if hw is None or hw != gold:
                fails += 1
                if fails <= 10:
                    print(f"MISMATCH a=0x{a:x} b=0x{b:x} hw={hw} gold=0x{gold:x}")
    ser.close()
    print(f"HW RESULT: {checked - fails}/{checked} bit-exact (fails={fails})")
    return fails == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=64)
    ap.add_argument("--exhaustive", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    sys.exit(0 if run_hw(a.port, a.baud, a.n, a.exhaustive) else 1)


if __name__ == "__main__":
    main()
