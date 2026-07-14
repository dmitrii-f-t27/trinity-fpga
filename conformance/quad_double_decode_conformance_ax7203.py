#!/usr/bin/env python3
# quad_double_decode_conformance_ax7203.py — Bailey/Hida quad-double (4x FP64) -> FP32 on AX7203.
# value = EXACT sum of four IEEE-754 binary64 limbs (l1..l4, l1 most-significant first);
# round RNE to binary32. Golden uses Fraction (exact dyadic). hi-limb specials propagate.
import argparse, sys, struct
from fractions import Fraction
FRAME = bytes([0xAA, 0x55])
FMT_QD = 0x28


def f64_decode(bits):
    bits &= (1 << 64) - 1
    sign = (bits >> 63) & 1
    exp = (bits >> 52) & 0x7FF
    mant = bits & ((1 << 52) - 1)
    if exp == 0x7FF:
        return ('nan', sign) if mant else ('inf', sign)
    if exp == 0:
        if mant == 0:
            return ('zero', sign)
        v = Fraction(mant, 1 << 1074)
    else:
        v = Fraction((1 << 52) | mant, 1 << 52) * (Fraction(2) ** (exp - 1023))
    return ('finite', v if sign == 0 else -v)


def to_f32(val):
    if val == 0:
        return 0
    sign = 0
    if val < 0:
        sign = 1; val = -val
    e = val.numerator.bit_length() - val.denominator.bit_length()
    while val < Fraction(2) ** e:
        e -= 1
    while val >= Fraction(2) ** (e + 1):
        e += 1
    if e > 127:
        return (sign << 31) | 0x7F800000
    if e < -150:
        return (sign << 31)
    if e >= -126:
        m = (val * (1 << 23)) / (Fraction(2) ** e)
        m_num, m_den = m.numerator, m.denominator
        fm = m_num // m_den
        rem = (m_num - fm * m_den) * 2
        if rem > m_den or (rem == m_den and (fm % 2 == 1)):
            fm += 1
        if fm >= (1 << 24):
            fm >>= 1; e += 1
        if e > 127:
            return (sign << 31) | 0x7F800000
        return (sign << 31) | ((e + 127) << 23) | (fm & 0x7FFFFF)
    k = val * (1 << 149)
    k_num, k_den = k.numerator, k.denominator
    fk = k_num // k_den
    rem = (k_num - fk * k_den) * 2
    if rem > k_den or (rem == k_den and (fk % 2 == 1)):
        fk += 1
    if fk == 0:
        return (sign << 31)
    if fk >= (1 << 23):
        return (sign << 31) | (1 << 23)
    return (sign << 31) | fk


def golden_quad_double(code256):
    limbs = [(code256 >> (64 * k)) & ((1 << 64) - 1) for k in range(4)]  # l1 = low 64
    decs = [f64_decode(l) for l in limbs]
    if any(d[0] == 'nan' for d in decs):
        return 0x7FC00000
    infs = [d for d in decs if d[0] == 'inf']
    if infs:
        s = sum(1 if d[1] == 0 else -1 for d in infs)
        if s == 0:           # mixed +inf and -inf -> NaN
            return 0x7FC00000
        return ((0 if s > 0 else 1) << 31) | 0x7F800000
    total = sum((d[1] if d[0] == 'finite' else Fraction(0)) for d in decs)
    return to_f32(total)


def hw_exchange(ser, code256):
    b = code256.to_bytes(32, 'little')
    pkt = FRAME + bytes([FMT_QD & 0xFF]) + b + bytes([0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return struct.unpack("<I", resp[1:5])[0]


def run_hw(port, baud, n):
    import serial, random
    ser = serial.Serial(port, baud, timeout=2); fails = 0; checked = 0; rnd = random.Random(17)
    F = 0x3FF0000000000000
    Fm = 0xBFF0000000000000
    INF = 0x7FF0000000000000
    NAN = 0x7FF8000000000000
    EPS = 0x3CB0000000000000
    corners = [F, (F << 64), (F << 128), (F << 64) | (F << 128) | (EPS << 192),
               Fm, INF, NAN, (F) | (EPS << 64) | (EPS << 128)]
    sample = corners + [rnd.getrandbits(256) for _ in range(max(0, n - len(corners)))]
    for code in sample:
        hw = hw_exchange(ser, code); gold = golden_quad_double(code); checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 10:
                print(f"MISMATCH code=0x{code:064x} hw=0x{hw if hw is not None else 0:08x} gold=0x{gold:08x}")
    ser.close(); print(f"HW RESULT: {checked - fails}/{checked} bit-exact (fails={fails})"); return fails == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=64)
    a = ap.parse_args()
    sys.exit(0 if run_hw(a.port, a.baud, a.n) else 1)


if __name__ == "__main__":
    main()
