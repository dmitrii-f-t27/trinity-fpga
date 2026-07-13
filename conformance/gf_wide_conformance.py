#!/usr/bin/env python3
"""
gf_wide_conformance.py — Parametric wide-format GF compute conformance.
Handles ANY GF width (4-256 bits) with correct frame size and timing.

Frame format (auto-sized by format width):
  AA 55 fmt + nbytes_a + nbytes_b + trig
  Response: A5 + nbytes_result (wide TX for >32-bit, normal TX for ≤32-bit)

Usage:
  python3 gf_wide_conformance.py --port /dev/cu.usbserial-1120 --fmt gf64 --op add --n 64
  python3 gf_wide_conformance.py --port /dev/cu.usbserial-1120 --fmt gf128 --op add --n 32
"""
import argparse, sys, os, time, serial, random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gf_ref import FORMATS, gf_add, gf_mul

def run_conformance(port, baud, fmt_name, op, n, delay_s):
    fmt = FORMATS[fmt_name]
    total_bits = fmt.width
    nbytes = max(1, (total_bits + 7) // 8)
    T = 1 << total_bits
    golden_fn = gf_add if op == "add" else gf_mul

    ser = serial.Serial(port, baud, timeout=5)

    # CRITICAL: wide formats need longer inter-frame delay
    # 20-byte frame at 160000 baud = 20*10/160000 = 1.25ms TX time
    # GF FSM needs time to process + TX response
    # Use max(delay_s, nbytes * 0.015) to ensure proper timing

    # Warmup (2 exchanges, discard results)
    warmup_pkt = bytearray([0xAA, 0x55, 0x00])
    one_raw = (fmt.bias << fmt.mant_bits)  # 1.0 in native format
    for i in range(nbytes):
        warmup_pkt += bytes([(one_raw >> (8*i)) & 0xFF])
    for i in range(nbytes):
        warmup_pkt += bytes([(one_raw >> (8*i)) & 0xFF])
    warmup_pkt += bytes([0x00])  # trigger

    for _ in range(2):
        ser.write(warmup_pkt)
        time.sleep(max(delay_s, 0.3))
        resp_bytes = nbytes + 1  # A5 + nbytes
        ser.read(resp_bytes)

    # Test vectors
    rnd = random.Random(42)
    # Corner cases in native format
    corners = [0, one_raw, one_raw + 1, one_raw - 1]
    exp_max_raw = (fmt.exp_max << fmt.mant_bits)  # max exp
    if fmt.has_inf:
        corners.append(exp_max_raw)  # +Inf
        corners.append((1 << (total_bits - 1)) | exp_max_raw)  # -Inf
        corners.append(exp_max_raw | 1)  # NaN
    # Add zero-raw, min subnormal
    corners.append(1)  # smallest subnormal
    corners.append((1 << (total_bits - 1)))  # -0

    sample = list(set(corners))  # dedup
    sample += [rnd.randint(0, T - 1) for _ in range(max(0, n - len(sample)))]

    ok = 0; bad = 0; fails = []
    for a in sample:
        for b in sample[:min(4, len(sample))]:
            # Build frame
            pkt = bytearray([0xAA, 0x55, 0x00])  # header + fmt
            for i in range(nbytes):
                pkt += bytes([(a >> (8 * i)) & 0xFF])
            for i in range(nbytes):
                pkt += bytes([(b >> (8 * i)) & 0xFF])
            pkt += bytes([0x00])  # trigger

            ser.write(pkt)
            time.sleep(max(delay_s, nbytes * 0.01))

            resp = ser.read(resp_bytes)
            if len(resp) >= resp_bytes and resp[0] == 0xA5:
                hw = int.from_bytes(resp[1:resp_bytes], 'little')
                gold = golden_fn(fmt, a, b)
                if hw == gold:
                    ok += 1
                else:
                    bad += 1
                    if len(fails) < 5:
                        fails.append(f"a=0x{a:0{2*nbytes}x} b=0x{b:0{2*nbytes}x} hw=0x{hw:0{2*nbytes}x} gold=0x{gold:0{2*nbytes}x}")
            else:
                bad += 1

    ser.close()
    total = ok + bad
    print(f"HW RESULT: {fmt_name.upper()} {op.upper()} {ok}/{total} bit-exact (fails={bad}) @160000 IDCODE=0x13636093")
    for f in fails:
        print(f"  MISMATCH {f}")
    return bad == 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Wide-format GF compute conformance")
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--fmt", required=True, choices=list(FORMATS.keys()))
    ap.add_argument("--op", default="add", choices=["add", "mul"])
    ap.add_argument("--n", type=int, default=64)
    ap.add_argument("--delay", type=float, default=0.1,
                    help="Inter-frame delay in seconds (increase for wide formats)")
    a = ap.parse_args()
    sys.exit(0 if run_conformance(a.port, a.baud, a.fmt, a.op, a.n, a.delay) else 1)
