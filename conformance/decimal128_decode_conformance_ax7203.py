#!/usr/bin/env python3
# decimal128_decode_conformance_ax7203.py — IEEE 754 decimal128 (BID) -> FP32 on AX7203.
# BID per Wikipedia decimal128: case A (bits[126:125]!=11) exp=bits[126:113](14b), C=bits[112:0](113b);
# case B (bits[126:125]==11, bits[126:123]!=1111) exp=bits[124:111](14b), C={100,bits[110:0]}(114b);
# special (bits[126:123]==1111): bit122=1 NaN, bit122=0 Inf. bias 6176.
# value = (-1)^s * C * 10^(E-6176), RNE to binary32 (Python Decimal oracle).
import argparse, sys, struct
from decimal import Decimal, ROUND_HALF_EVEN, localcontext

FRAME = bytes([0xAA, 0x55])
FMT_DECIMAL128 = 0x29
MASK128 = (1 << 128) - 1


def _bid128_decode(code):
    code &= MASK128
    sign = (code >> 127) & 1
    if ((code >> 125) & 0x3) != 0b11:                    # case A
        exp = (code >> 113) & 0x3FFF
        C = code & ((1 << 113) - 1)
        return ('finite', sign, C, exp)
    if ((code >> 123) & 0xF) == 0b1111:                  # special
        return ('nan', sign) if ((code >> 122) & 1) else ('inf', sign)
    exp = (code >> 111) & 0x3FFF                          # case B, bits[124:111]
    C = (0b100 << 111) | (code & ((1 << 111) - 1))        # {100, bits[110:0]}, 114-bit
    return ('finite', sign, C, exp)


def _dec_to_fp32(sign, d):
    if d == 0:
        return sign << 31
    with localcontext() as ctx:
        ctx.prec = 80
        a = d
        e = int((a.ln() / Decimal(2).ln()).to_integral_value(rounding=ROUND_HALF_EVEN))
        two_e = Decimal(2) ** e
        while a < two_e:
            e -= 1; two_e = Decimal(2) ** e
        while a >= two_e * 2:
            e += 1; two_e = Decimal(2) ** e
        if e > 127:
            return (sign << 31) | 0x7F800000
        if e >= -126:
            m = (a / two_e) * (1 << 23)
            m_int = int(m.to_integral_value(rounding=ROUND_HALF_EVEN))
            if m_int >= (1 << 24):
                m_int >>= 1; e += 1
                if e > 127:
                    return (sign << 31) | 0x7F800000
            return (sign << 31) | ((e + 127) << 23) | (m_int & 0x7FFFFF)
        k = a * (Decimal(2) ** 149)
        k_int = int(k.to_integral_value(rounding=ROUND_HALF_EVEN))
        if k_int == 0:
            return sign << 31
        if k_int >= (1 << 23):
            return (sign << 31) | (1 << 23)
        return (sign << 31) | k_int


def golden_decimal128(code):
    kind = _bid128_decode(code)
    if kind[0] == 'inf':
        return (kind[1] << 31) | 0x7F800000
    if kind[0] == 'nan':
        return (kind[1] << 31) | 0x7FC00000
    _, sign, C, E = kind
    if C == 0:
        return sign << 31
    de = E - 6176
    with localcontext() as ctx:
        ctx.prec = 80
        d = Decimal(C) * (Decimal(10) ** de)
    return _dec_to_fp32(sign, d)


def _enc128(sign, C, E):
    if C < (1 << 113):
        return (sign << 127) | (E << 113) | C
    assert (C >> 111) == 0b100
    return (sign << 127) | (0b11 << 125) | (E << 111) | (C & ((1 << 111) - 1))


T27 = {
    _enc128(0, 1, 6176): 0x3F800000,
    _enc128(1, 1, 6176): 0xBF800000,
    _enc128(0, 2, 6176): 0x40000000,
    _enc128(0, 5, 6175): 0x3F000000,
    _enc128(0, 1, 6177): 0x41200000,
    _enc128(0, 1, 6175): 0x3DCCCCCD,
    _enc128(0, 1 << 113, 6176): 0x78000000,
    0x78000000000000000000000000000000: 0x7F800000,
    0x7C000000000000000000000000000000: 0x7FC00000,
}


def hw_exchange(ser, code):
    b = code.to_bytes(16, 'little')
    pkt = FRAME + bytes([FMT_DECIMAL128 & 0xFF]) + b + bytes([0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return struct.unpack("<I", resp[1:5])[0]


def run_hw(port, baud, n):
    import serial, random
    ser = serial.Serial(port, baud, timeout=2); fails = 0; checked = 0; rnd = random.Random(29)
    sample = list(T27.keys()) + [rnd.randint(0, MASK128) for _ in range(max(0, n - len(T27)))]
    for code in sample:
        hw = hw_exchange(ser, code); gold = golden_decimal128(code); checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 10:
                print(f"MISMATCH code=0x{code:032x} hw=0x{hw if hw is not None else 0:08x} gold=0x{gold:08x}")
    ser.close(); print(f"HW RESULT: {checked - fails}/{checked} bit-exact (fails={fails})"); return fails == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbserial-120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=64)
    a = ap.parse_args()
    sys.exit(0 if run_hw(a.port, a.baud, a.n) else 1)


if __name__ == "__main__":
    main()
