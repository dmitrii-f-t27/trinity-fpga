#!/usr/bin/env python3
"""GF256 decode conformance — GoldenFloat(256,97,158) BIAS=2^96-1 → FP32. 32-byte frame."""
import struct, random, argparse

N, E, M = 256, 97, 158
BIAS = (1 << (E - 1)) - 1
EM = (1 << E) - 1
MM = (1 << M) - 1

def decode(raw):
    raw &= (1 << N) - 1
    s = raw >> (N - 1)
    e = (raw >> M) & EM
    m = raw & MM
    if e == EM:
        if m == 0: return 0xFF800000 if s else 0x7F800000
        return 0x7FC00001
    if e == 0:
        if m == 0: return s << 31
        v = (m / float(1 << M)) * (2.0 ** (1 - BIAS))
    else:
        v = (1 + m / float(1 << M)) * (2.0 ** (e - BIAS))
    try:
        if abs(v) > 3.4e38: return 0xFF800000 if v < 0 else 0x7F800000
        return struct.unpack(">I", struct.pack(">f", -v if s else v))[0]
    except (OverflowError, ValueError):
        return 0xFF800000 if s else 0x7F800000

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbserial-120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=100)
    args = ap.parse_args()
    import serial, time
    codes = set()
    codes.add(0); codes.add(1 << 255)  # ±0
    codes.add(EM << M); codes.add((1 << 255) | (EM << M))  # ±Inf
    codes.add((EM << M) | 1)  # NaN
    # Normal values near 1.0 (exp ≈ BIAS) — these fit in FP32
    for de in [-200, -127, -1, 0, 1, 127, 200]:
        e = BIAS + de
        if 1 <= e < EM:
            for mv in [0, 1, MM, max(0, MM // 2)]:
                for s in [0, 1]:
                    codes.add((s << 255) | (e << M) | mv)
    # Subnormal
    for mv in [1, MM, max(0, MM // 2)]:
        codes.add(mv); codes.add((1 << 255) | mv)
    # Random (only test values that produce representable FP32)
    rng = random.Random(256)
    while len(codes) < args.n + 20:
        raw = rng.randrange(1 << N)
        g = decode(raw)
        if g != 0 and g != 0x7F800000 and g != 0xFF800000 and g != 0x7FC00001:
            codes.add(raw)
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
            if (gn and dn) or d == g: ok += 1
            else:
                if len(fails) < 10: fails.append(f"gold={g:#010x} hw={d:#010x}")
        else:
            if len(fails) < 10: fails.append("noresp")
    print(f"HW RESULT: {ok}/{len(codes)} bit-exact (fails={len(codes)-ok})")
    for f in fails: print(f"  {f}", file=sys.stderr)
    port.close()

if __name__ == "__main__":
    main()
