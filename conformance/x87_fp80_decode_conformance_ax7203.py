#!/usr/bin/env python3
"""x87_fp80 decode conformance — 80-bit extended → FP32. 16-byte frame (upper 6 bytes=0)."""
import serial, struct, time, random, sys, math, argparse

def decode(raw128):
    raw = raw128 & ((1<<80)-1)  # take lower 80 bits
    sign = raw >> 79
    exp = (raw >> 64) & 0x7FFF
    mant = raw & ((1<<64)-1)
    int_bit = (mant >> 63) & 1
    if mant == 0 and exp == 0: return sign << 31
    if exp == 0x7FFF: return 0x7FC00000  # Inf/NaN → qNaN
    if exp == 0 and int_bit == 0:
        # Pseudo-denormal or zero exp → underflow
        return sign << 31
    exp32 = exp - 16256  # excess-16383 → excess-127
    mant_pre = (mant >> 40) & 0x7FFFFF
    guard = (mant >> 39) & 1
    sticky = 1 if (mant & ((1<<39)-1)) else 0
    round_up = guard and (sticky or (mant_pre & 1))
    mant_rnd = mant_pre + (1 if round_up else 0)
    if mant_rnd > 0x7FFFFF:
        mant_rnd = 0; exp32 += 1
    if exp32 > 254: return (sign<<31)|0x7F800000
    if exp32 < 1: return sign<<31
    return (sign<<31)|((exp32&0xFF)<<23)|(mant_rnd&0x7FFFFF)

def make_codes():
    codes = set()
    codes.add(0)
    # +1.0 = 3FFF8000000000000000
    codes.add(0x3FFF8000000000000000)
    codes.add(0xBFFF8000000000000000)  # -1.0
    for e in [1,0x3FFF,0x4000,0x7FFE]:
        for m in [0x8000000000000000,0xC000000000000000,0xFFFFFFFFFFFFFFFF]:
            v = (e<<64)|m
            codes.add(v); codes.add(v|0x80000000000000000000)
    # +Inf, not pseudo-INF: the integer bit (0x8000...) is SET. Pseudo-infinity is the
    # same exponent with it CLEAR, and is an invalid operand rather than a value. Both
    # belong in the sweep, so both are here now.
    codes.add(0x7FFF8000000000000000)  # +Inf
    codes.add(0xFFFF8000000000000000)  # -Inf
    codes.add(0x7FFFC000000000000000)  # quiet NaN
    codes.add(0x7FFF0000000000000000)  # pseudo-infinity (integer bit clear: invalid)
    codes.add(0x7FFF0000000000000001)  # pseudo-NaN     (integer bit clear: invalid)
    codes.add(0x0000800000000000)      # unnormal-adjacent low pattern
    rng = random.Random(80)
    for _ in range(2000): codes.add(rng.randrange(1<<80))
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
        # Send 16 bytes (lower 10 = code, upper 6 = 0)
        b = [(raw >> (i*8)) & 0xFF for i in range(16)]
        port.write(bytes([0xAA,0x55,0x00]+b+[0x00]))
        time.sleep(0.006)
        r = port.read(5)
        if len(r)>=5 and r[0]==0xA5:
            d = r[1]|(r[2]<<8)|(r[3]<<16)|(r[4]<<24)
            gn = (g>>23&0xFF)==0xFF and g&0x7FFFFF
            dn = (d>>0x23&0xFF)==0xFF and d&0x7FFFFF
            if gn and dn or d==g: ok+=1
            else:
                if len(fails)<10: fails.append(f"raw={raw:#022x} g={g:#010x} d={d:#010x}")
        else:
            if len(fails)<10: fails.append(f"raw={raw:#022x} noresp")
    print(f"HW RESULT: {ok}/{len(codes)} bit-exact (fails={len(codes)-ok})")
    for f in fails: print(f"  {f}", file=sys.stderr)
    port.close()

if __name__ == "__main__": main()
