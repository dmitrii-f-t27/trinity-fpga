#!/usr/bin/env python3
"""lns64 decode conformance — 64-bit LNS (scale 128) → FP32."""
import serial, struct, time, random, sys, argparse
SCALE = 128
def decode(raw):
    raw &= (1<<64)-1
    sign = raw >> 63
    if raw == 0 or (raw & ((1<<63)-1)) == 0: return sign << 31
    signed_log = raw & ((1<<63)-1)
    if signed_log & (1<<62): signed_log -= (1<<63)
    val = (-1)**sign * 2.0**(signed_log / SCALE)
    if abs(val) > 3.4e38: return 0xFF800000 if val < 0 else 0x7F800000
    if abs(val) < 1.2e-38: return sign << 31
    return struct.unpack(">I", struct.pack(">f", val))[0]
def make_codes():
    codes = set([0, 0x8000000000000000])
    for log in range(-1024, 1024, 8):
        raw = log & ((1<<63)-1)
        codes.add(raw); codes.add(raw | (1<<63))
    rng = random.Random(64)
    for _ in range(2000): codes.add(rng.randrange(1<<64))
    return sorted(codes)
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbserial-120")
    ap.add_argument("--baud", type=int, default=160000)
    args = ap.parse_args()
    codes = make_codes()
    port = serial.Serial(args.port, args.baud, timeout=3)
    ok = 0; fails = []
    for raw in codes:
        g = decode(raw)
        b = [(raw >> (i*8)) & 0xFF for i in range(8)]
        port.write(bytes([0xAA,0x55,0x00]+b+[0x00]))
        time.sleep(0.005)
        r = port.read(5)
        if len(r)>=5 and r[0]==0xA5:
            d = r[1]|(r[2]<<8)|(r[3]<<16)|(r[4]<<24)
            if d==g: ok+=1
            else:
                if len(fails)<10: fails.append(f"raw={raw:#018x} g={g:#010x} d={d:#010x}")
        else:
            if len(fails)<10: fails.append(f"raw={raw:#018x} noresp")
    print(f"HW RESULT: {ok}/{len(codes)} bit-exact (fails={len(codes)-ok})")
    for f in fails: print(f"  {f}", file=sys.stderr)
    port.close()
if __name__ == "__main__": main()
