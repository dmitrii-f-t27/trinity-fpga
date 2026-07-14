#!/usr/bin/env python3
# gf10_add_conformance_ax7203.py — GF10 ADD compute-conformance on AX7203.
# ADD(a,b) via gf_adder_param #(3,6), no flip. Golden = gf_ref.gf_add(GF10, a, b).
import argparse, sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gf_ref import FORMATS, gf_add

GFMT = FORMATS["gf10"]         # 1S+3E+6M, bias=3, HAS_INF=0
T = 1 << 10


def golden_add(a, b):
    return gf_add(GFMT, a, b)


FRAME = bytes([0xAA, 0x55])


def hw_exchange(ser, a, b):
    pkt = FRAME + bytes([a & 0xFF, (a >> 8) & 0xFF, b & 0xFF, (b >> 8) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(4)
    if len(resp) != 4 or resp[0] != 0xA5:
        return None
    return resp[1] | (resp[2] << 8)


def self_test():
    rnd = random.Random(42)
    bad = 0
    for _ in range(3000):
        a = rnd.randint(0, T - 1)
        if a in (0x000, 0x200):            # +/-0: a+0 -> +0 (IEEE zero-sign), != a
            continue
        if golden_add(a, 0) != a:
            bad += 1
    spot = golden_add(0x100, 0x100)        # 2.0 + 2.0 -> 4.0
    print(f"self-test: a+0==a over 3000 random (skip +/-0), {bad} failures; gf10_add(0x100,0x100)=0x{spot:03x} (expect 0x140)")
    return bad == 0 and spot == 0x140


def run_hw(port, baud, n):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0; checked = 0
    rnd = random.Random(42)
    corners = [0x000, 0x001, 0x3FF, 0x200, 0x100, 0x1C0, 0x300, 0x2FF]
    sample = corners + [rnd.randint(0, T - 1) for _ in range(max(0, n - len(corners)))]
    for a in sample:
        for b in sample[:8]:
            hw = hw_exchange(ser, a, b)
            gold = golden_add(a, b)
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
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    sys.exit(0 if run_hw(a.port, a.baud, a.n) else 1)


if __name__ == "__main__":
    main()
