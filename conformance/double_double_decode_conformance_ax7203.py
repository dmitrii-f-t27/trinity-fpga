#!/usr/bin/env python3
# double_double_decode_conformance_ax7203.py — Bailey/Hida double-double -> FP32 on AX7203.
# value = EXACT sum of two IEEE-754 binary64 limbs (hi, lo; hi most-significant first),
# rounded RNE to binary32. Golden uses fractions.Fraction (exact dyadic, no double-round).
# hi-limb specials propagate; inf-inf / inf+(-inf) -> NaN; lo-limb specials propagate too.
import argparse, sys, struct
from fractions import Fraction
FRAME = bytes([0xAA, 0x55])
FMT_DD = 0x27
MASK64 = (1 << 64) - 1


def f64_decode(bits):
    """Return ('finite', signed Fraction) | ('inf', sign) | ('nan', sign) | ('zero', sign)."""
    bits &= MASK64
    sign = (bits >> 63) & 1
    exp = (bits >> 52) & 0x7FF
    mant = bits & ((1 << 52) - 1)
    if exp == 0x7FF:
        return ('nan', sign) if mant else ('inf', sign)
    if exp == 0:
        if mant == 0:
            return ('zero', sign)
        v = Fraction(mant, 1 << 1074)                 # subnormal: mant * 2^-1074
    else:
        v = Fraction((1 << 52) | mant, 1 << 52) * (Fraction(2) ** (exp - 1023))
    return ('finite', v if sign == 0 else -v)


def to_f32(val):
    """Round a Fraction val (may be negative) to binary32 RNE bits."""
    if val == 0:
        return 0
    sign = 0
    if val < 0:
        sign = 1; val = -val
    # find e with 2^e <= val < 2^(e+1) (val = num/den, exact). Fraction(2)**k handles k<0.
    num, den = val.numerator, val.denominator
    e = num.bit_length() - den.bit_length()
    while val < Fraction(2) ** e:
        e -= 1
    while val >= Fraction(2) ** (e + 1):
        e += 1
    if e > 127:
        return (sign << 31) | 0x7F800000
    if e < -150:
        return (sign << 31)
    if e >= -126:
        # mantissa = val/2^e * 2^23 in [2^23, 2^24)
        m = (val * (1 << 23)) / (Fraction(2) ** e)        # Fraction
        m_num, m_den = m.numerator, m.denominator
        floor_m = m_num // m_den
        rem = (m_num - floor_m * m_den) * 2
        # RNE: compare 2*rem vs m_den
        if rem > m_den or (rem == m_den and (floor_m % 2 == 1)):
            floor_m += 1
        if floor_m >= (1 << 24):
            floor_m >>= 1; e += 1
        if e > 127:
            return (sign << 31) | 0x7F800000
        return (sign << 31) | ((e + 127) << 23) | (floor_m & 0x7FFFFF)
    # subnormal: k = round(val * 2^149)
    k = val * (1 << 149)
    k_num, k_den = k.numerator, k.denominator
    floor_k = k_num // k_den
    rem = (k_num - floor_k * k_den) * 2
    if rem > k_den or (rem == k_den and (floor_k % 2 == 1)):
        floor_k += 1
    if floor_k == 0:
        return (sign << 31)
    if floor_k >= (1 << 23):
        return (sign << 31) | (1 << 23)                  # smallest normal
    return (sign << 31) | floor_k


def golden_double_double(code128):
    hi = f64_decode(code128 & MASK64)
    lo = f64_decode((code128 >> 64) & MASK64)
    if hi[0] == 'nan' or lo[0] == 'nan':
        return 0x7FC00000
    if hi[0] == 'inf' and lo[0] == 'inf' and hi[1] != lo[1]:
        return 0x7FC00000                                  # inf + (-inf) -> NaN
    if hi[0] == 'inf':
        return (hi[1] << 31) | 0x7F800000
    if lo[0] == 'inf':
        return (lo[1] << 31) | 0x7F800000
    hv = hi[1] if hi[0] == 'finite' else Fraction(0)
    lv = lo[1] if lo[0] == 'finite' else Fraction(0)
    return to_f32(hv + lv)


def hw_exchange(ser, code128):
    b = code128.to_bytes(16, 'little')
    pkt = FRAME + bytes([FMT_DD & 0xFF]) + b + bytes([0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return struct.unpack("<I", resp[1:5])[0]


def run_hw(port, baud, n):
    import serial, random
    ser = serial.Serial(port, baud, timeout=2); fails = 0; checked = 0; rnd = random.Random(13)
    # corners: hi=1.0/lo=0 (+1), hi=1.0/lo=eps, hi=-1.0/lo=0, hi=Inf, hi=NaN, subnormal mixes
    F64_1 = 0x3FF0000000000000; F64_m1 = 0xBFF0000000000000; F64_INF = 0x7FF0000000000000
    F64_NAN = 0x7FF8000000000000; F64_PI = 0x400921FB54442D18; F64_EPS = 0x3CB0000000000000
    corners = [F64_1, (F64_1 << 64), (F64_m1 << 64), F64_INF, F64_NAN,
               F64_PI | (F64_EPS << 64), (F64_PI << 64) | F64_EPS]
    sample = corners + [rnd.getrandbits(128) for _ in range(max(0, n - len(corners)))]
    for code in sample:
        hw = hw_exchange(ser, code); gold = golden_double_double(code); checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 10:
                print(f"MISMATCH code=0x{code:032x} hw=0x{hw if hw is not None else 0:08x} gold=0x{gold:08x}")
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
