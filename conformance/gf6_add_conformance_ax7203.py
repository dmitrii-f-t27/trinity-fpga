#!/usr/bin/env python3
"""GF6 e2m3 ADD compute-conformance on AX7203 (1S+2E+3M, bias=1).

Golden oracle lives in gf_ref.py (parametric, Fraction-exact, RNE + gradual
underflow). This script is now a thin HW harness around it; the previous
inline integer reference was verified bit-exact against gf_ref.py over the
full 64x64 grid before removal (see conformance/compute_golden_consistency.py
history).
"""
import sys, os, argparse, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "conformance")
from gf8_add_conformance_ax7203 import hw_exchange
from gf_ref import FORMATS, gf_add

E, M, BIAS = 2, 3, 1
TOTAL = 1 + E + M  # 6
FMT = FORMATS["gf6"]


def self_test():
    rnd = random.Random(42)
    sample = [0x00, 0x01, 0x3F, 0x20, 0x10, 0x30, 0x0F, 0x08]
    sample += [rnd.randint(0, (1 << TOTAL) - 1) for _ in range(56)]
    bad = checked = 0
    for a in sample:
        for b in sample[:8]:
            g = gf_add(FMT, a, b)
            checked += 1
            if not (0 <= g < (1 << TOTAL)):
                bad += 1
            if gf_add(FMT, a, b) != gf_add(FMT, b, a):
                bad += 1
    print(f"self-test: {checked}-pair GF6 golden, in-width+commutative, bad={bad}")
    return bad == 0


def run_hw(port, baud):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    rnd = random.Random(42)
    sample = [0x00, 0x01, 0x3F, 0x20, 0x10, 0x30, 0x0F, 0x08]
    sample += [rnd.randint(0, 63) for _ in range(56)]
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
