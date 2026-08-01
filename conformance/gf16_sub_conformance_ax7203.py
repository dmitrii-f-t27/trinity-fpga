#!/usr/bin/env python3
# gf16_sub_conformance_ax7203.py — GF16 SUB compute-conformance on AX7203.
# SUB(a,b) = ADD(a,-b). Flashed design (fpga/vivado/gf16_sub_ax7203.v) flips b's
# sign bit (bit 15) then runs gf_adder_param #(6,9,HAS_INF=1) — silicon-PROVEN for
# ADD (512/512, NaN fix). Golden = gf_ref.gf_add(GF16, a, b ^ 0x8000). (GF16 ADD is
# the HAS_INF track, not formal-PROVEN — SUB rests on the same silicon evidence.)
#
#   self-test:   python3 gf16_sub_conformance_ax7203.py --self-test
#   on hardware: python3 gf16_sub_conformance_ax7203.py --port /dev/cu.usbserial-1120 --baud 160000
import argparse, sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gf_ref import FORMATS, gf_add

GFMT = FORMATS["gf16"]         # 1S+6E+9M, bias=31, HAS_INF=1
SIGN = 1 << (GFMT.exp_bits + GFMT.mant_bits)   # sign bit = 0x8000 for GF16
T = 1 << (GFMT.exp_bits + GFMT.mant_bits + 1)  # 65536


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
    # so it validates the sign-mask + format wiring without the 4B-pair blowup.
    # Plus corner no-crash + a spot-check.
    rnd = random.Random(42)
    corners = [0x0000, 0x0001, 0x7C00, 0x7C01, 0xFC00, 0xFFFF, SIGN, 0x3C00, 0x4000]
    bad = 0
    for a in corners:                       # corner no-crash
        for b in corners:
            _ = golden_sub(a, b)
    for _ in range(3000):                   # a - 0 == a  (the core identity)
        a = rnd.randint(0, T - 1)
        # Skip NaN a: NaN + (-0) = canonical quiet-NaN (≠ a's payload) — correct
        # IEEE propagation, not a wiring bug. (GF16 is the only SUB width with NaN.)
        is_nan = ((a & 0x7C00) == 0x7C00) and ((a & 0x03FF) != 0)
        if not is_nan and golden_sub(a, 0) != a:
            bad += 1
    spot = golden_sub(0x3C00, 0x3C00)        # finite a: a - a -> +0 (1.0 - 1.0)
    print(f"self-test: a-0==a over 3000 random + corner no-crash, {bad} failures; "
          f"gf16_sub(0x3C00,0x3C00)=0x{spot:04x} (expect 0x0000)")
    return bad == 0 and spot == 0


def run_hw(port, baud, n, exhaustive=False):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0; checked = 0
    rnd = random.Random(42)
    if exhaustive:
        sample = list(range(T))      # 65536 (representative; full 65536^2 is huge)
    else:
        sample = [0x0000, 0x0001, 0x7C00, 0x7C01, 0xFC00, 0xFFFF, SIGN, 0x3C00]
        sample += [rnd.randint(0, T - 1) for _ in range(n - len(sample))]
    for a in sample:
        for b in (sample[:8]):
            hw = hw_exchange(ser, a, b)
            gold = golden_sub(a, b)
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
    ap.add_argument("--exhaustive", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    sys.exit(0 if run_hw(a.port, a.baud, a.n, a.exhaustive) else 1)


if __name__ == "__main__":
    main()
