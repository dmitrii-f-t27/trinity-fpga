#!/usr/bin/env python3
# gf14_mul_conformance_ax7203.py — GF14 MUL compute-conformance on AX7203.
# MUL(a,b) via gf_mul_param #(5,8), no flip. Golden = gf_ref.gf_mul(GF14, a, b).
import argparse, sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gf_ref import FORMATS, gf_mul

GFMT = FORMATS["gf14"]         # 1S+5E+8M, bias=15, HAS_INF=0
ONE  = GFMT.bias << GFMT.mant_bits   # gf14 1.0 = 15<<8 = 0x0F00
T = 1 << 14


def golden_mul(a, b):
    return gf_mul(GFMT, a, b)


FRAME = bytes([0xAA, 0x55])  # magic only — the gf compute wrappers have no fmt byte


def hw_exchange(ser, a, b):
    pkt = FRAME + bytes([a & 0xFF, (a >> 8) & 0xFF, b & 0xFF, (b >> 8) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(4)
    if len(resp) != 4 or resp[0] != 0xA5:
        return None
    return resp[1] | (resp[2] << 8)


def self_test():
    # GF14 has no Inf/NaN -> a*1==a holds for ALL inputs (incl +/-0: 0*1=0, -0*1=-0).
    rnd = random.Random(42)
    bad = 0
    for _ in range(3000):
        a = rnd.randint(0, T - 1)
        if golden_mul(a, ONE) != a:
            bad += 1
    spot = golden_mul(0x1000, ONE)          # 2.0 * 1.0 -> 2.0
    print(f"self-test: a*1==a over 3000 random, {bad} failures; gf14_mul(0x1000,0x{ONE:04x})=0x{spot:04x} (expect 0x1000)")
    return bad == 0 and spot == 0x1000


def run_hw(port, baud, n):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0; checked = 0
    rnd = random.Random(42)
    corners = [0x0000, 0x0001, 0x3FFF, 0x2000, 0x1000, 0x3000, 0x0F00, 0x2F00]
    sample = corners + [rnd.randint(0, T - 1) for _ in range(max(0, n - len(corners)))]
    for a in sample:
        for b in sample[:8]:
            hw = hw_exchange(ser, a, b)
            gold = golden_mul(a, b)
            checked += 1
            if hw is None or hw != gold:
                fails += 1
                if fails <= 10:
                    print(f"MISMATCH a=0x{a:04x} b=0x{b:04x} hw={hw} gold=0x{gold:04x}")
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
