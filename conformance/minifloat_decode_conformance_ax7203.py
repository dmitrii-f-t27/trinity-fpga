#!/usr/bin/env python3
"""Minifloat E3M4 decode conformance — 8-bit (1+3+4, bias=3) → FP32. 1-byte frame."""
import serial, struct, time, random, sys, argparse

E, M, BIAS = 3, 4, 3
EM = (1 << E) - 1
MM = (1 << M) - 1

def decode(raw):
    raw &= 0xFF
    s = raw >> 7
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
    return struct.unpack(">I", struct.pack(">f", -v if s else v))[0]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=256)
    args = ap.parse_args()

    codes = list(range(256))
    port = serial.Serial(args.port, args.baud, timeout=3)
    ok = 0; fails = []
    for raw in codes:
        g = decode(raw)
        b = [raw & 0xFF]
        port.write(bytes([0xAA, 0x55, 0] + b + [0]))
        time.sleep(0.005)
        r = port.read(5)
        if len(r) >= 5 and r[0] == 0xA5:
            d = r[1] | (r[2] << 8) | (r[3] << 16) | (r[4] << 24)
            gn = (g >> 23 & 0xFF) == 0xFF and (g & 0x7FFFFF)
            dn = (d >> 23 & 0xFF) == 0xFF and (d & 0x7FFFFF)
            if (gn and dn) or d == g:
                ok += 1
            else:
                if len(fails) < 10:
                    fails.append(f"raw={raw:#04x} gold={g:#010x} hw={d:#010x}")
        else:
            if len(fails) < 10:
                fails.append(f"raw={raw:#04x} noresp")
    print(f"HW RESULT: {ok}/256 bit-exact (fails={256-ok})")
    for f in fails:
        print(f"  {f}", file=sys.stderr)
    port.close()

if __name__ == "__main__":
    main()
