#!/usr/bin/env python3
# gf12_sub_conformance_ax7203.py — GF12 SUB compute-conformance on AX7203.
# SUB(a,b) = ADD(a,-b). Flashed design (fpga/vivado/gf12_sub_ax7203.v) flips b's
# sign bit (bit 11) then runs gf_adder_param #(4,7) — formal-PROVEN for ADD (all
# pairs) + silicon-PROVEN. Golden = gf_ref.gf_add(GF12, a, b ^ 0x800).
#
#   self-test:   python3 gf12_sub_conformance_ax7203.py --self-test
#   on hardware: python3 gf12_sub_conformance_ax7203.py --port /dev/cu.usbserial-1120 --baud 160000
import argparse, sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gf_ref import FORMATS, gf_add

GFMT = FORMATS["gf12"]         # 1S+4E+7M, bias=7, HAS_INF=0
SIGN = 1 << (GFMT.exp_bits + GFMT.mant_bits)   # sign bit = 0x800 for GF12
T = 1 << (GFMT.exp_bits + GFMT.mant_bits + 1)  # 4096


def golden_sub(a, b):
    return gf_add(GFMT, a, b ^ SIGN)


FRAME = bytes([0xAA, 0x55])  # magic only — the gf compute wrappers have no fmt byte


def hw_exchange(ser, a, b):
    # LE 16-bit words (lo, hi) to match the wrapper's op_a[7:0]/op_a[15:8] FSM.
    pkt = FRAME + bytes([a & 0xFF, (a >> 8) & 0xFF, b & 0xFF, (b >> 8) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(4)
    if len(resp) != 4 or resp[0] != 0xA5:
        return None
    return resp[1] | (resp[2] << 8)   # result_y[7:0], result_y[15:8] (LE)


def self_test():
    # Fast + meaningful: a-0=a holds for ALL inputs (x + (-0) = x, incl Inf/NaN),
    # so it cleanly validates the sign-mask + format wiring without the 16M-pair
    # blowup. Plus corner no-crash + a spot-check.
    rnd = random.Random(42)
    corners = [0x000, 0x001, 0x7FF, 0xFFF, SIGN, 0x400, 0x800 | 1, 0x300]
    bad = 0
    for a in corners:                       # corner no-crash
        for b in corners:
            _ = golden_sub(a, b)
    for _ in range(3000):                   # a - 0 == a  (the core identity)
        a = rnd.randint(0, T - 1)
        if golden_sub(a, 0) != a:
            bad += 1
    spot = golden_sub(0x400, 0x400)          # finite a: a - a -> +0
    print(f"self-test: a-0==a over 3000 random + corner no-crash, {bad} failures; "
          f"gf12_sub(0x400,0x400)=0x{spot:03x} (expect 0x000)")
    return bad == 0 and spot == 0


def run_hw(port, baud, n, exhaustive=False):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0; checked = 0
    rnd = random.Random(42)
    if exhaustive:
        sample = list(range(T))      # 4096 (representative; full 4096^2 is large)
    else:
        sample = [0x000, 0x001, 0x7FF, 0xFFF, SIGN, 0x400, 0x300, 0xB00]
        sample += [rnd.randint(0, T - 1) for _ in range(n - len(sample))]
    for a in sample:
        for b in (sample[:8]):
            hw = hw_exchange(ser, a, b)
            gold = golden_sub(a, b)
            checked += 1
            if hw is None or hw != gold:
                fails += 1
                if fails <= 10:
                    print(f"MISMATCH a=0x{a:03x} b=0x{b:03x} hw={hw} gold=0x{gold:03x}")
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
