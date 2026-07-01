#!/usr/bin/env python3
# lns16_decode_conformance_ax7203.py — 16-bit LNS decode on AX7203.
# 1 sign + 15-bit signed log (2's complement, scale 128). Antilog via 128-entry LUT.
# Golden = struct.pack FP32 of 2^(signed_log/128). Validated against 5 t27 vectors.
import argparse, sys, struct, serial, random

FRAME = bytes([0xAA, 0x55])
FMT_LNS16 = 0x18

T27_VECTORS = {
    0x0000: 0x00000000,  # 0.0
    0x8000: 0xBF800000,  # -1.0
    0x0080: 0x40000000,  # 2.0
    0x7F80: 0x3F000000,  # 0.5
    0x0100: 0x40800000,  # 4.0
}


def golden_lns16(code):
    code &= 0xFFFF
    if code == 0x0000:
        return 0x00000000
    sign = (code >> 15) & 1
    log_field = code & 0x7FFF
    signed_log = log_field if log_field < 16384 else log_field - 32768
    value = 2.0 ** (signed_log / 128.0)
    if sign:
        value = -value
    return struct.unpack('>I', struct.pack('>f', value))[0]


def hw_exchange(ser, code):
    pkt = FRAME + bytes([FMT_LNS16 & 0xFF, code & 0xFF, (code >> 8) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return struct.unpack("<I", resp[1:5])[0]


def self_test():
    bad = 0
    for code, exp in T27_VECTORS.items():
        g = golden_lns16(code)
        if g != exp:
            bad += 1; print(f"  0x{code:04x}: golden=0x{g:08x} expected=0x{exp:08x}")
    print(f"self-test: golden vs {len(T27_VECTORS)} t27 vectors, {bad} failures")
    return bad == 0


def run_hw(port, baud, n):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0; checked = 0
    rnd = random.Random(42)
    corners = list(T27_VECTORS.keys()) + [0x0040, 0x7FC0, 0x8001, 0xFF80]
    sample = corners + [rnd.randint(0, 0xFFFF) for _ in range(max(0, n - len(corners)))]
    for code in sample:
        hw = hw_exchange(ser, code)
        gold = golden_lns16(code)
        checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 10:
                print(f"MISMATCH code=0x{code:04x} hw=0x{hw if hw is not None else 0:08x} gold=0x{gold:08x}")
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
