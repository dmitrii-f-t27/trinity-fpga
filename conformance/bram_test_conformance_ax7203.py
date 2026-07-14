#!/usr/bin/env python3
"""BRAM INIT diagnostic conformance. Verifies 1024×32-bit table read."""
import serial, time, sys, argparse

def decode(addr):
    addr &= 0x3FF
    if addr < 32:
        return 1 << addr
    return 0  # entries 32+ are uninitialized

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    args = ap.parse_args()

    port = serial.Serial(args.port, args.baud, timeout=3)
    ok = 0; fails = []
    for addr in range(32):
        g = decode(addr)
        b = [addr & 0xFF, (addr >> 8) & 0xFF]
        port.write(bytes([0xAA, 0x55, 0] + b + [0]))
        time.sleep(0.005)
        r = port.read(5)
        if len(r) >= 5 and r[0] == 0xA5:
            d = r[1] | (r[2] << 8) | (r[3] << 16) | (r[4] << 24)
            if d == g:
                ok += 1
                print(f"  addr={addr:2d} gold=0x{g:08x} hw=0x{d:08x} OK")
            else:
                fails.append(f"addr={addr:2d} gold=0x{g:08x} hw=0x{d:08x} MISMATCH")
                print(f"  addr={addr:2d} gold=0x{g:08x} hw=0x{d:08x} MISMATCH")
        else:
            fails.append(f"addr={addr:2d} noresp")
    print(f"\nBRAM INIT: {ok}/32 correct")
    if fails:
        print("BRAM INIT IS BROKEN — entries do not match expected values")
    else:
        print("BRAM INIT WORKS — all 32 entries correct")
    port.close()

if __name__ == "__main__":
    main()
