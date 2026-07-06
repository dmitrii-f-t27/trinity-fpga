import random
#!/usr/bin/env python3
"""ibm_hfp128 decode conformance — 16-byte frame → FP32."""
import serial, struct, time, random, sys, argparse


def decode(raw):
    raw &= (1<<128)-1
    sign = raw >> 127
    exp = (raw >> 120) & 0x7F
    frac = raw & ((1<<120)-1)
    if exp == 0 and frac == 0: return sign << 31
    if frac == 0: return sign << 31
    lead = frac.bit_length() - 1
    exp_base2 = 4*(exp-64) - 120 + lead + 127
    fsh = frac << (119 - lead)
    mant = (fsh >> 96) & 0x7FFFFF
    if exp_base2 > 254: return (sign<<31)|0x7F800000
    if exp_base2 < 1: return sign<<31
    return (sign<<31)|((exp_base2&0xFF)<<23)|mant

def make_codes():
    codes = set()
    codes.add(0)
    for e in range(0,128,8):
        for f in [1,0xFF,0xFFFF]:
            v = (e<<120)|f
            codes.add(v); codes.add(v|0x80000000000000000000000000000000)
    codes.add(0x4040F0AC0000000000000000000000)  # ~3.0 IBM
    rng = random.Random(128)
    for _ in range(2000): codes.add(rng.randrange(1<<128))
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
        b = [(raw >> (i*8)) & 0xFF for i in range(16)]
        port.write(bytes([0xAA,0x55,0x00]+b+[0x00]))
        time.sleep(0.006)
        r = port.read(5)
        if len(r)>=5 and r[0]==0xA5:
            d = r[1]|(r[2]<<8)|(r[3]<<16)|(r[4]<<24)
            gn = (g>>23&0xFF)==0xFF and g&0x7FFFFF
            dn = (d>>23&0xFF)==0xFF and d&0x7FFFFF
            if gn and dn or d==g: ok+=1
            else:
                if len(fails)<10: fails.append(f"raw={raw:#034x} g={g:#010x} d={d:#010x}")
        else:
            if len(fails)<10: fails.append(f"raw={raw:#034x} noresp")
    print(f"HW RESULT: {ok}/{len(codes)} bit-exact (fails={len(codes)-ok})")
    for f in fails: print(f"  {f}", file=sys.stderr)
    port.close()
