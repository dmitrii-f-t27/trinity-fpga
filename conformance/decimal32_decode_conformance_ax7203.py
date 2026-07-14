#!/usr/bin/env python3
# decimal32_decode_conformance_ax7203.py — IEEE 754 decimal32 (BID) -> FP32 decode on AX7203.
# BID combination-field decode per IEEE 754-2008 (Wikipedia decimal32):
#   case A (bits[30:29]!=11): exp=bits[30:23] (8b), C=bits[22:0] (23b).
#   case B (bits[30:29]==11, bits[30:27]!=1111): exp=bits[28:21] (8b), C={100,bits[20:0]} (24b).
#   special (bits[30:27]==1111): bit26=1 NaN, bit26=0 Inf.
#   value = (-1)^s * C * 10^(E-101), RNE to binary32 (Python Decimal oracle, exact).
import argparse, sys, struct
from decimal import Decimal, ROUND_HALF_EVEN, localcontext

FRAME = bytes([0xAA, 0x55])
FMT_DECIMAL32 = 0x24
MASK32 = (1 << 32) - 1


def _bid32_decode(code):
    """Return ('finite', sign, C, E) | ('inf', sign) | ('nan', sign)."""
    code &= MASK32
    sign = (code >> 31) & 1
    if ((code >> 29) & 0x3) != 0b11:                 # case A
        exp = (code >> 23) & 0xFF
        C = code & 0x7FFFFF                           # 23 bits
        return ('finite', sign, C, exp)
    if ((code >> 27) & 0xF) == 0b1111:               # special
        return ('nan', sign) if ((code >> 26) & 1) else ('inf', sign)
    exp = (code >> 21) & 0xFF                         # case B, bits[28:21]
    C = 0x800000 | (code & 0x1FFFFF)                  # {100, bits[20:0]}, 24 bits
    return ('finite', sign, C, exp)


def _dec_to_fp32(sign, d):
    """Exact RNE of non-negative finite Decimal d to binary32 bits (sign applied)."""
    if d == 0:
        return sign << 31
    with localcontext() as ctx:
        ctx.prec = 60
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


def golden_decimal32(code):
    kind = _bid32_decode(code)
    if kind[0] == 'inf':
        return (kind[1] << 31) | 0x7F800000
    if kind[0] == 'nan':
        return (kind[1] << 31) | 0x7FC00000
    _, sign, C, E = kind
    if C == 0:
        return sign << 31
    de = E - 101
    with localcontext() as ctx:
        ctx.prec = 60
        d = Decimal(C) * (Decimal(10) ** de)
    return _dec_to_fp32(sign, d)


def _enc32(sign, C, E):
    """Encode finite decimal32 BID (case A if C < 2^23, else case B)."""
    if C < (1 << 23):
        return (sign << 31) | (E << 23) | C
    # case B: C in [2^23, 2^24), bits[23:21] must be "100" for a valid decimal32 coeff
    assert (C >> 21) == 0b100, f"case B coeff top3 must be 100, got C=0x{C:x}"
    return (sign << 31) | (0b11 << 29) | (E << 21) | (C & 0x1FFFFF)


# Hand-derived (sign, C, E) -> decimal32 code; expected FP32 from the VALUE (independent).
T27 = {
    _enc32(0, 1, 101): 0x3F800000,        # +1.0
    _enc32(1, 1, 101): 0xBF800000,        # -1.0
    _enc32(0, 2, 101): 0x40000000,        # +2.0
    _enc32(0, 3, 101): 0x40400000,        # +3.0
    _enc32(0, 5, 100): 0x3F000000,        # +0.5 (5e-1)
    _enc32(0, 1, 102): 0x41200000,        # +10.0 (1e1)
    _enc32(0, 1, 100): 0x3DCCCCCD,        # +0.1 (1e-1) -> nearest binary32
    _enc32(0, 1 << 23, 101): 0x4B000000,  # +2^23 (case B, leading "100"); FP32 exp 23
    0x78000000: 0x7F800000,               # +Inf  (bits30:27=1111, bit26=0)
    0x7C000000: 0x7FC00000,               # quiet NaN (bit26=1)
}


def hw_exchange(ser, code):
    b = code.to_bytes(4, 'little')
    pkt = FRAME + bytes([FMT_DECIMAL32 & 0xFF]) + b + bytes([0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return struct.unpack("<I", resp[1:5])[0]


def self_test():
    bad = 0
    for code, exp in T27.items():
        g = golden_decimal32(code)
        if g != exp:
            bad += 1
            print(f"  0x{code:08x}: golden=0x{g:08x} exp=0x{exp:08x}")
    print(f"self-test: golden vs {len(T27)} hand-derived vectors (BID case A/B + inf/nan), {bad} failures")
    return bad == 0


def run_hw(port, baud, n):
    import serial, random
    ser = serial.Serial(port, baud, timeout=2); fails = 0; checked = 0; rnd = random.Random(7)
    sample = list(T27.keys()) + [rnd.randint(0, MASK32) for _ in range(max(0, n - len(T27)))]
    for code in sample:
        hw = hw_exchange(ser, code); gold = golden_decimal32(code); checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 10:
                print(f"MISMATCH code=0x{code:08x} hw=0x{hw if hw is not None else 0:08x} gold=0x{gold:08x}")
    ser.close(); print(f"HW RESULT: {checked - fails}/{checked} bit-exact (fails={fails})"); return fails == 0


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
