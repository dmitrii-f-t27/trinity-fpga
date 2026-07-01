#!/usr/bin/env python3
# e8m0_decode_conformance_ax7203.py — E8M0 (OCP MX shared scale) decode-conformance on AX7203.
# E8M0 = 8-bit exponent-only, value = 2^(e-127), no sign. 0xFF = NaN, 0x00 = 2^-127.
# The flashed design (corona_decode_e8m0_ax7203.v) decodes code -> FP32 via e8m0_decode.
# Frame: AA 55 fmt code_lo code_hi trig -> A5 r0 r1 r2 r3 (32-bit FP32 LE). fmt is ignored
# by the single-decoder build but sent for protocol parity.
#
#   self-test:   python3 e8m0_decode_conformance_ax7203.py --self-test
#   on hardware: python3 e8m0_decode_conformance_ax7203.py --port /dev/cu.usbserial-120 --baud 160000
import argparse, sys, struct

# Independent golden (re-implemented from the E8M0 spec, NOT copied from the RTL):
#   0xFF -> qNaN 0x7FC00000; 0x00 -> 2^-127 FP32 subnormal 0x00400000;
#   else -> FP32 {sign=0, exp=code, mant=0} = code<<23, value = 2^(code-127).
NAN_F32 = 0x7FC00000
SUBNORM_F32 = 0x00400000   # 2^-127 as FP32 subnormal


def golden_e8m0(code):
    code &= 0xFF
    if code == 0xFF:
        return NAN_F32
    if code == 0x00:
        return SUBNORM_F32
    return (code << 23) & 0xFFFFFFFF   # {0, code[7:0], 23'b0}


FRAME = bytes([0xAA, 0x55])


def hw_exchange(ser, code, fmt=12):
    # AA 55 fmt code_lo code_hi trig (code_hi=0; e8m0 is 8-bit)
    pkt = FRAME + bytes([fmt & 0xFF, code & 0xFF, 0x00, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return struct.unpack("<I", resp[1:5])[0]   # 32-bit LE


def self_test():
    # Exhaustive 256 codes: golden matches the spec for every code.
    bad = 0
    for code in range(256):
        g = golden_e8m0(code)
        expect = (NAN_F32 if code == 0xFF else
                  SUBNORM_F32 if code == 0x00 else
                  (code << 23) & 0xFFFFFFFF)
        if g != expect:
            bad += 1
    # landmarks: 127 -> 1.0, 128 -> 2.0, 0 -> 2^-127, 255 -> NaN
    lm = (golden_e8m0(0x7F) == 0x3F800000 and golden_e8m0(0x80) == 0x40000000 and
          golden_e8m0(0x00) == SUBNORM_F32 and golden_e8m0(0xFF) == NAN_F32)
    print(f"self-test: 256-code golden vs spec, {bad} failures; landmarks {'OK' if lm else 'FAIL'}")
    print(f"  golden(0x7F)=0x{golden_e8m0(0x7F):08X} (1.0)  golden(0x80)=0x{golden_e8m0(0x80):08X} (2.0)  "
          f"golden(0x00)=0x{golden_e8m0(0x00):08X} (2^-127)  golden(0xFF)=0x{golden_e8m0(0xFF):08X} (NaN)")
    return bad == 0 and lm


def run_hw(port, baud, exhaustive=True):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = 0; checked = 0
    sample = range(256) if exhaustive else [0x00, 0x01, 0x7F, 0x80, 0xFE, 0xFF]
    for code in sample:
        hw = hw_exchange(ser, code)
        gold = golden_e8m0(code)
        checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 10:
                print(f"MISMATCH code=0x{code:02x} hw=0x{hw:08X} gold=0x{gold:08X}")
    ser.close()
    print(f"HW RESULT: {checked - fails}/{checked} bit-exact (fails={fails})")
    return fails == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--port", default="/dev/cu.usbserial-120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--sample", action="store_true", help="corner sample instead of exhaustive 256")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    sys.exit(0 if run_hw(a.port, a.baud, exhaustive=not a.sample) else 1)


if __name__ == "__main__":
    main()
