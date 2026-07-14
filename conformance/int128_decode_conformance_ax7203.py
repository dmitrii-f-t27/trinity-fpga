#!/usr/bin/env python3
"""int128 decode conformance — signed 128-bit int → FP32. 16-byte frame."""
import serial, struct, time, random, sys, argparse

def int128_to_fp32(raw):
    """128-bit raw → signed → FP32 bits."""
    if raw >= (1 << 127):
        val = raw - (1 << 128)
    else:
        val = raw
    f = float(val)
    return struct.unpack('>I', struct.pack('>f', f))[0]

def make_codes():
    codes = set()
    codes.add(0); codes.add(1); codes.add((1<<128)-1)  # 0, +1, -1
    for p in range(0, 128, 8):
        codes.add(1 << p)
        codes.add((1<<128) - (1 << p))  # -(2^p)
    codes.add((1<<127)-1)  # max positive
    codes.add(1<<127)      # min negative (-2^127)
    codes.add(2**24); codes.add(2**24+1)
    rng = random.Random(128)
    for _ in range(2000):
        codes.add(rng.randrange(1 << 128))
    return sorted(codes)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', default='/dev/cu.usbserial-1120')
    ap.add_argument('--baud', type=int, default=160000)
    args = ap.parse_args()
    codes = make_codes()
    port = serial.Serial(args.port, args.baud, timeout=2)
    ok = 0; fails = []
    for raw in codes:
        golden = int128_to_fp32(raw)
        b = [(raw >> (i*8)) & 0xFF for i in range(16)]
        port.write(bytes([0xAA, 0x55, 0x00] + b + [0x00]))
        time.sleep(0.006)
        resp = port.read(5)
        if len(resp) >= 5 and resp[0] == 0xA5:
            dut = resp[1] | (resp[2]<<8) | (resp[3]<<16) | (resp[4]<<24)
            if dut == golden: ok += 1
            else:
                if len(fails) < 10: fails.append(f"raw={raw:#034x} g={golden:#010x} d={dut:#010x}")
        else:
            if len(fails) < 10: fails.append(f"raw={raw:#034x} noresp")
    print(f"HW RESULT: {ok}/{len(codes)} bit-exact (fails={len(codes)-ok})")
    for f in fails: print(f"  {f}", file=sys.stderr)
    port.close()

if __name__ == '__main__':
    main()
