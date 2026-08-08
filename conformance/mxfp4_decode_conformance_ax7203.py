#!/usr/bin/env python3
"""mxfp4 decode conformance — 4-bit → FP32. 2-byte frame."""
import serial, struct, time, random, sys, argparse
N,E,M,BIAS = 4,2,1,1
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from gf_decode_golden import decode_to_fp32
EM = (1<<E)-1
def decode(raw):
    # Exact golden -- conformance/gf_decode_golden.py.
    # This used to do `if e==EM: e=EM-1; m=(1<<M)-1  # saturate (OCP MX: no Inf/NaN)`.
    # The comment is right and the code does not follow it: OCP MX FP4 E2M1 has no
    # Inf, no NaN and no reserved code, so exp=all-ones is an ordinary value. The
    # codebook is {0, .5, 1, 1.5, 2, 3, 4, 6} and saturating mapped both 4 and 6
    # onto 3 -- codes 6, 7, 14 and 15, a quarter of the format.
    return decode_to_fp32(raw, N, E, M, BIAS, "mxfp4")
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--port",default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud",type=int,default=160000)
    args=ap.parse_args()
    codes=set()
    MMAX=(1<<M)-1
    for s in (0,1):
        codes.add(s<<(N-1)); codes.add((s<<(N-1))|(EM<<M))
    codes.add((EM<<M)|1); codes.add((EM<<M)|MMAX)
    for s in (0,1):
        for mv in [1,MMAX,max(1,MMAX//2)]:
            codes.add((s<<(N-1))|mv)
    for e in [1,2,max(2,BIAS%EM),EM-1]:
        if 1<=e<EM:
            for mv in [0,MMAX,max(0,MMAX//2)]:
                for s in (0,1): codes.add((s<<(N-1))|(e<<M)|mv)
    rng=random.Random(4)
    for _ in range(min(2000,(1<<N)-1)): codes.add(rng.randrange(1<<N))
    codes=sorted(codes)
    port=serial.Serial(args.port,args.baud,timeout=3)
    ok=0; fails=[]
    for raw in codes:
        g=decode(raw)
        port.write(bytes([0xAA,0x55,0,raw&0xFF,(raw>>8)&0xFF,0]))
        time.sleep(0.004)
        r=port.read(5)
        if len(r)>=5 and r[0]==0xA5:
            d=r[1]|(r[2]<<8)|(r[3]<<16)|(r[4]<<24)
            gn=(g>>23&0xFF)==0xFF and g&0x7FFFFF
            dn=(d>>23&0xFF)==0xFF and d&0x7FFFFF
            if gn and dn or d==g: ok+=1
            else:
                if len(fails)<5: fails.append(f"raw={raw:#x} g={g:#010x} d={d:#010x}")
        else:
            if len(fails)<5: fails.append(f"raw={raw:#x} noresp")
    print(f"HW RESULT: {ok}/{len(codes)} bit-exact (fails={len(codes)-ok})")
    for f in fails: print(f"  {f}",file=sys.stderr)
    port.close()
if __name__=="__main__": main()
