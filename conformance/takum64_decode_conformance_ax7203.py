#!/usr/bin/env python3
# takum64_decode_conformance_ax7203.py — takum64 (Hunhold 2024, N=64) -> FP32 on AX7203.
# Same decode law as takum16/32, scaled to N=64. value = (-1)^S * exp(ell/2).
import argparse, sys, struct
import mpmath
mpmath.mp.prec = 400
N = 64
_C_BIAS = [-255,-127,-63,-31,-15,-7,-3,-1, 0,1,3,7,15,31,63,127]
FRAME = bytes([0xAA, 0x55])
FMT_TAKUM64 = 0x2B


def ell_exact(b):
    if b == 0: return (0, None, "zero")
    if b == (1 << (N-1)): return (0, None, "nar")
    S = (b >> (N-1)) & 1
    D = (b >> (N-2)) & 1
    R_uint = (b >> (N-5)) & 7
    c_bias = _C_BIAS[(D << 3) | R_uint]
    r_eff = (7 - R_uint) if D == 0 else R_uint
    p = N - r_eff - 5
    if p < 0: p = 0
    lower = b & ((1 << (r_eff + p)) - 1)
    M_uint = (lower & ((1 << p) - 1)) if p > 0 else 0
    C_uint = ((lower >> p) & ((1 << r_eff) - 1)) if r_eff > 0 else 0
    c = c_bias + C_uint
    m = mpmath.mpf(M_uint) / mpmath.mpf(2 ** p) if p > 0 else mpmath.mpf(0)
    ell = (1 - 2 * S) * (mpmath.mpf(c) + m)
    return (S, ell, "normal")


def to_f32(r):
    if r == 0: return 0
    sign = 0
    if r < 0: sign = 1; r = -r
    two = mpmath.mpf(2)
    if r >= two**128: return (sign<<31) | 0x7F800000
    if r < two**(-150): return (sign<<31)
    e = int(mpmath.floor(mpmath.log(r, 2)))
    while two**e > r: e -= 1
    while two**(e+1) <= r: e += 1
    if e >= -126:
        mant = r / two**e * two**23
        fm = int(mpmath.floor(mant)); frac = mant - fm
        if (frac > mpmath.mpf('0.5')) or (frac == mpmath.mpf('0.5') and (fm % 2 == 1)): fm += 1
        if fm >= (1<<24): fm >>= 1; e += 1
        if e > 127: return (sign<<31) | 0x7F800000
        return (sign<<31) | ((e+127)<<23) | (fm & 0x7FFFFF)
    k = r * two**149
    fk = int(mpmath.floor(k)); frac = k - fk
    if (frac > mpmath.mpf('0.5')) or (frac == mpmath.mpf('0.5') and (fk % 2 == 1)): fk += 1
    if fk == 0: return (sign<<31)
    if fk >= (1<<23): return (sign<<31) | (1<<23)
    return (sign<<31) | fk


def golden_takum64(b):
    S, ell, cat = ell_exact(b)
    if cat == "zero": return 0
    if cat == "nar":  return 0x7FC00000
    r = mpmath.e ** (ell / 2)
    r = -r if S else r
    return to_f32(r)


def hw_exchange(ser, code):
    b = code.to_bytes(8, 'little')
    pkt = FRAME + bytes([FMT_TAKUM64 & 0xFF]) + b + bytes([0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5: return None
    return struct.unpack("<I", resp[1:5])[0]


def run_hw(port, baud, n):
    import serial, random
    ser = serial.Serial(port, baud, timeout=2); fails = 0; checked = 0; rnd = random.Random(41)
    F = 1 << (N-2)  # 1.0: D=1 bit set
    corners = [0, F, F|(1<<63), 1<<63, 1, 2, F+1]
    sample = corners + [rnd.getrandbits(N) for _ in range(max(0, n - len(corners)))]
    for code in sample:
        hw = hw_exchange(ser, code); gold = golden_takum64(code); checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 10: print(f"MISMATCH code=0x{code:016x} hw=0x{hw if hw is not None else 0:08x} gold=0x{gold:08x}")
    ser.close(); print(f"HW RESULT: {checked-fails}/{checked} bit-exact (fails={fails})"); return fails == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbserial-120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=64)
    a = ap.parse_args()
    sys.exit(0 if run_hw(a.port, a.baud, a.n) else 1)


if __name__ == "__main__":
    main()
