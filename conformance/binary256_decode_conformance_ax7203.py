#!/usr/bin/env python3
"""Binary256 decode conformance — IEEE octuple → FP32. 32-byte data frame."""
import serial, struct, time, random, sys, argparse

N = 256
E_BITS = 19
M_BITS = 236
BIAS = (1 << (E_BITS - 1)) - 1  # 262143
EMAX = (1 << E_BITS) - 1

def decode(raw):
    raw &= (1 << N) - 1
    sign = raw >> (N - 1)
    exp = (raw >> M_BITS) & EMAX
    mant = raw & ((1 << M_BITS) - 1)
    if exp == EMAX:
        if mant == 0:
            return 0xFF800000 if sign else 0x7F800000
        return 0x7FC00001
    if exp == 0:
        return sign << 31
    unbiased = exp - BIAS
    fp32_biased = unbiased + 127
    if fp32_biased >= 255:
        return 0xFF800000 if sign else 0x7F800000
    if fp32_biased <= 0:
        return sign << 31
    mant23 = mant >> (M_BITS - 23)
    return (sign << 31) | (fp32_biased << 23) | mant23

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbserial-120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=200)
    args = ap.parse_args()

    codes = set()
    # Special values
    codes.add(0)  # +0
    codes.add(1 << 255)  # -0
    codes.add(EMAX << M_BITS)  # +Inf
    codes.add((1 << 255) | (EMAX << M_BITS))  # -Inf
    codes.add((EMAX << M_BITS) | 1)  # NaN

    # Values in FP32 range: exp near BIAS
    for e in [BIAS-200, BIAS-127, BIAS-1, BIAS, BIAS+1, BIAS+127, BIAS+200]:
        for m in [0, 1, (1 << 236) - 1, (1 << 235)]:
            for s in [0, 1]:
                raw = (s << 255) | (e << M_BITS) | m
                codes.add(raw)

    # Overflow/underflow
    for e in [1, 2, BIAS-300, BIAS+300, EMAX-1]:
        codes.add(e << M_BITS)
        codes.add((1 << 255) | (e << M_BITS))

    # Random
    rng = random.Random(256)
    for _ in range(args.n):
        codes.add(rng.randrange(1 << N))

    codes = sorted(codes)
    port = serial.Serial(args.port, args.baud, timeout=5)
    ok = 0; fails = []
    nbytes = 32
    for raw in codes:
        g = decode(raw)
        b = [(raw >> (i * 8)) & 0xFF for i in range(nbytes)]
        port.write(bytes([0xAA, 0x55, 0] + b + [0]))
        time.sleep(0.008)
        r = port.read(5)
        if len(r) >= 5 and r[0] == 0xA5:
            d = r[1] | (r[2] << 8) | (r[3] << 16) | (r[4] << 24)
            gn = (g >> 23 & 0xFF) == 0xFF and (g & 0x7FFFFF)
            dn = (d >> 23 & 0xFF) == 0xFF and (d & 0x7FFFFF)
            if (gn and dn) or d == g:
                ok += 1
            else:
                if len(fails) < 10:
                    fails.append(f"raw=0x{raw:064x} gold={g:#010x} hw={d:#010x}")
        else:
            if len(fails) < 10:
                fails.append(f"raw=0x{raw:064x} noresp")
    print(f"HW RESULT: {ok}/{len(codes)} bit-exact (fails={len(codes)-ok})")
    for f in fails:
        print(f"  {f}", file=sys.stderr)
    port.close()

if __name__ == "__main__":
    main()
