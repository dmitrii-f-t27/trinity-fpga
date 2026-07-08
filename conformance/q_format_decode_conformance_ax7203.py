#!/usr/bin/env python3
"""Q1.15 fixed-point decode conformance — int16(raw)/2^15 → FP32. 2-byte frame."""
import serial, struct, time, random, sys, argparse

QN = 15

def decode(raw):
    raw &= 0xFFFF
    sval = raw - 65536 if raw >= 32768 else raw
    val = sval / float(1 << QN)
    return struct.unpack(">I", struct.pack(">f", val))[0]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbserial-120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=256)
    args = ap.parse_args()

    codes = set()
    codes.add(0x0000)  # +0
    codes.add(0x8000)  # -1.0
    codes.add(0x7FFF)  # max positive
    codes.add(0x8001)  # min negative
    codes.add(0x4000)  # 0.5
    codes.add(0xC000)  # -0.5
    codes.add(0x2000)  # 0.25
    codes.add(0x6000)  # 0.75
    codes.add(0xA000)  # -0.75
    codes.add(0x1000)  # 0.0625
    codes.add(0x3333)  # ~0.4
    codes.add(0xCCCD)  # ~-0.8
    rng = random.Random(42)
    for _ in range(args.n):
        codes.add(rng.randrange(65536))
    codes = sorted(codes)

    port = serial.Serial(args.port, args.baud, timeout=3)
    ok = 0; fails = []
    for raw in codes:
        g = decode(raw)
        b = [raw & 0xFF, (raw >> 8) & 0xFF]
        port.write(bytes([0xAA, 0x55, 0] + b + [0]))
        time.sleep(0.005)
        r = port.read(5)
        if len(r) >= 5 and r[0] == 0xA5:
            d = r[1] | (r[2] << 8) | (r[3] << 16) | (r[4] << 24)
            if d == g:
                ok += 1
            else:
                if len(fails) < 10:
                    fails.append(f"raw={raw:#06x} gold={g:#010x} hw={d:#010x}")
        else:
            if len(fails) < 10:
                fails.append(f"raw={raw:#06x} noresp")
    print(f"HW RESULT: {ok}/{len(codes)} bit-exact (fails={len(codes)-ok})")
    for f in fails:
        print(f"  {f}", file=sys.stderr)
    port.close()

if __name__ == "__main__":
    main()
