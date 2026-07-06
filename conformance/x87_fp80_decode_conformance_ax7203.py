#!/usr/bin/env python3
"""x87_fp80 decode conformance — 16-byte frame → FP32."""
import serial, struct, time, random, sys, argparse

def decode(raw):
    """Override in subclass."""
    raise NotImplementedError

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
