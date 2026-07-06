#!/usr/bin/env python3
"""
int64_decode_conformance_ax7203.py — HW conformance for int64 → FP32 decode.
Sends 64-bit codes via 8-byte frame, receives FP32, compares vs Python golden.

Golden: struct.pack('>f', float(int64_value)) — standard C library RNE rounding.
5-class coverage + edge cases + representative random sweep.
"""
import serial, struct, time, random, sys, argparse

def int64_to_fp32(raw):
    raw &= (1 << 64) - 1  # mask to 64-bit unsigned
    """int64 raw bits → FP32 bits via Python float (RNE rounding)."""
    # Interpret as signed 64-bit
    if raw >= (1 << 63):
        val = raw - (1 << 64)
    else:
        val = raw
    f = float(val)
    if abs(f) > 3.4028235e38:
        return 0xFF800000 if f < 0 else 0x7F800000
    return struct.unpack('>I', struct.pack('>f', f))[0]

def make_codes():
    codes = set()
    # zero
    codes.add(0)
    # ±1
    codes.add(1)
    codes.add((1<<64)-1)  # -1
    # powers of 2
    for p in range(0, 64, 4):
        codes.add(1 << p)
        codes.add(((1<<64)-1) - ((1<<p)-1))  # -(2^p)
    # FP32 boundary values
    codes.add(2**24)    # exactly representable
    codes.add(2**24+1)  # needs rounding
    codes.add(2**127)   # near FP32 max
    codes.add(2**128-1) # overflow → Inf
    codes.add((1<<64)-(2**128-1))  # -overflow
    # max int64
    codes.add((1<<63)-1)
    codes.add(1<<63)  # min int64 (-2^63)
    # random representative
    rng = random.Random(64)
    for _ in range(2000):
        codes.add(rng.randrange(1 << 64))
    return sorted(codes)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', default='/dev/cu.usbserial-120')
    ap.add_argument('--baud', type=int, default=160000)
    ap.add_argument('--n', type=int, default=0, help='limit vectors (0=all)')
    args = ap.parse_args()

    codes = make_codes()
    if args.n > 0:
        codes = codes[:args.n]

    port = serial.Serial(args.port, args.baud, timeout=2)
    ok = 0
    fails = []
    for raw in codes:
        golden = int64_to_fp32(raw)
        # Pack as 8 bytes (little-endian, matching wrapper code_r assignment)
        b = [(raw >> (i*8)) & 0xFF for i in range(8)]
        frame = bytes([0xAA, 0x55, 0x00] + b + [0x00])
        port.write(frame)
        time.sleep(0.005)
        resp = port.read(5)
        if len(resp) >= 5 and resp[0] == 0xA5:
            dut = resp[1] | (resp[2]<<8) | (resp[3]<<16) | (resp[4]<<24)
            if dut == golden:
                ok += 1
            else:
                if len(fails) < 10:
                    fails.append(f"raw={raw:#018x} golden={golden:#010x} dut={dut:#010x}")
        else:
            if len(fails) < 10:
                fails.append(f"raw={raw:#018x} no response ({len(resp)} bytes)")

    print(f"HW RESULT: {ok}/{len(codes)} bit-exact (fails={len(codes)-ok})")
    for f in fails:
        print(f"  FAIL {f}", file=sys.stderr)
    port.close()

if __name__ == '__main__':
    main()
