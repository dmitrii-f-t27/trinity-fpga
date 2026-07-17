#!/usr/bin/env python3
"""GF12 ADD compute-conformance on AX7203 (1S+4E+7M, bias=7).

Golden oracle lives in gf_ref.py (parametric, Fraction-exact, RNE + gradual
underflow). The previous inline integer reference was verified bit-exact
against gf_ref.py before removal.
"""
import sys, os, argparse, random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gf_ref import FORMATS, gf_add

E, M, BIAS = 4, 7, 7
TOTAL = 1 + E + M  # 12
FMT = FORMATS["gf12"]
FRAME = bytes([0xAA, 0x55, 0x00])  # AA 55 fmt


def hw_exchange(ser, a, b):
    pkt = FRAME + bytes([a & 0xFF, (a >> 8) & 0xFF, b & 0xFF, (b >> 8) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(4)
    if len(resp) != 4 or resp[0] != 0xA5:
        return None
    return resp[1] | (resp[2] << 8)


def self_test():
    rnd = random.Random(42)
    corners = [0x000, 0x001, 0x7FF, 0x400, 0x3C0, 0x3FF, 0x010, 0x100]
    sample = corners + [rnd.randint(0, (1 << TOTAL) - 1) for _ in range(56)]
    bad = checked = 0
    for a in sample:
        for b in sample[:8]:
            g = gf_add(FMT, a, b)
            checked += 1
            if not (0 <= g < (1 << TOTAL)):
                bad += 1
            if gf_add(FMT, a, b) != gf_add(FMT, b, a):
                bad += 1
    print(f"self-test: {checked}-pair GF12 golden, in-width+commutative, bad={bad}")
    return bad == 0


def run_hw(port, baud):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    rnd = random.Random(42)
    corners = [0x000, 0x001, 0x7FF, 0x400, 0x3C0, 0x3FF, 0x010, 0x100]
    sample = corners + [rnd.randint(0, (1 << TOTAL) - 1) for _ in range(56)]
    fails = checked = 0
    for a in sample:
        for b in sample[:8]:
            hw = hw_exchange(ser, a, b)
            g = gf_add(FMT, a, b)
            checked += 1
            if hw is None or hw != g:
                fails += 1
                if fails <= 10:
                    print(f"MISMATCH a={a} b={b} hw={hw} gold={g}")
    ser.close()
    print(f"HW RESULT: {checked-fails}/{checked} bit-exact (fails={fails})")
    return fails == 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    sys.exit(0 if run_hw(a.port, a.baud) else 1)
