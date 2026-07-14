#!/usr/bin/env python3
"""vax_h decode conformance — VAX H_floating (128-bit) → FP32."""
import serial, struct, time, random, sys, argparse

def decode(raw):
    raw &= (1<<128)-1
    sign = raw >> 127
    exp = (raw >> 112) & 0x7FFF
    mant = raw & ((1<<112)-1)
    if exp == 0: return sign << 31
    exp32 = exp - 16257  # excess-16384 → excess-127
    if exp32 > 254: return (sign<<31)|0x7F800000
    if exp32 < 1: return sign<<31
    mant_pre = (mant >> 89) & 0x7FFFFF
    guard = (mant >> 88) & 1
    sticky = 1 if (mant & ((1<<88)-1)) else 0
    round_up = guard and (sticky or (mant_pre & 1))
    mant_rnd = mant_pre + (1 if round_up else 0)
    if mant_rnd > 0x7FFFFF:
        mant_rnd = 0; exp32 += 1
    if exp32 > 254: return (sign<<31)|0x7F800000
    return (sign<<31)|((exp32&0xFF)<<23)|(mant_rnd&0x7FFFFF)

def make_codes():
    codes = set()
    codes.add(0); codes.add(0x80000000000000000000000000000000)
    for e in [1,2,0x1000,0x2000,0x3FFF,0x3FFE]:
        for m in [0,1,(1<<112)-1,(1<<111)]:
            v = (e<<112)|m
            codes.add(v); codes.add(v|0x80000000000000000000000000000000)
    rng = random.Random(128)
    for _ in range(2000): codes.add(rng.randrange(1<<128))
    return sorted(codes)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    args = ap.parse_args()
    codes = make_codes()
    port = serial.Serial(args.port, args.baud, timeout=3)
    ok = 0; fails = []
    for raw in codes:
        g = decode(raw)
        b = [(raw >> (i*8)) & 0xFF for i in range(16)]
        port.write(bytes([0xAA,0x55,0x00]+b+[0x00]))
        time.sleep(0.006)
        r = port.read(5)
        if len(r)>=5 and r[0]==0xA5:
            d = r[1]|(r[2]<<8)|(r[3]<<16)|(r[4]<<24)
            if d==g: ok+=1
            else:
                if len(fails)<10: fails.append(f"raw={raw:#034x} g={g:#010x} d={d:#010x}")
        else:
            if len(fails)<10: fails.append(f"raw={raw:#034x} noresp")
    print(f"HW RESULT: {ok}/{len(codes)} bit-exact (fails={len(codes)-ok})")
    for f in fails: print(f"  {f}", file=sys.stderr)
    port.close()

if __name__ == "__main__": main()
