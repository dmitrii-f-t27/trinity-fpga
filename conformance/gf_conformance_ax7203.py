#!/usr/bin/env python3
"""Parameterized GoldenFloat HW-conformance harness for AX7203.
Works with ANY GF pack (GF4..GF16) that has format_spec + test_vectors.
The FPGA design (gf16_clean_ax7203) echoes the 16-bit operand unchanged
(identity a+0=a), so the same bitstream works for all GF widths ≤16 bits.
"""
import argparse, json, math, sys
from pathlib import Path

def gf_encode(value, sign_bits, exp_bits, mant_bits, exp_bias):
    if value == 0.0: return 0
    sign = 1 if value < 0.0 else 0
    av = abs(value)
    exp = int(math.floor(math.log2(av)))
    mant = round((av / (2.0 ** exp) - 1.0) * (1 << mant_bits))
    if mant == (1 << mant_bits):
        mant = 0; exp += 1
    exp_field = (exp + exp_bias) & ((1 << exp_bits) - 1)
    return (sign << (exp_bits + mant_bits)) | (exp_field << mant_bits) | mant

def run(pack_path, device, baud, limit):
    with open(pack_path) as f:
        pack = json.load(f)
    spec = pack["format_spec"]
    sb, eb, mb, bias = spec["sign_bits"], spec["exp_bits"], spec["mant_bits"], spec["exp_bias"]
    fmt_name = pack.get("format_name", "?")
    print(f"\nFormat: {fmt_name} ({sb}S+{eb}E+{mb}M, bias={bias})")

    import serial
    port = serial.Serial(device, baud, timeout=2)
    vectors = pack["test_vectors"]
    if limit: vectors = vectors[:limit]
    fails = 0
    for i, v in enumerate(vectors):
        val = v["input"]["value"]
        a = gf_encode(val, sb, eb, mb, bias)
        frame = bytes([0xAA, 0x55, a & 0xFF, (a >> 8) & 0xFF, 0, 0, 0])
        port.write(frame); port.flush()
        resp = port.read(4)
        if len(resp) < 4:
            print(f"FAIL[{i}] {v['name']}: short response ({len(resp)} bytes)")
            fails += 1; continue
        result = resp[1] | (resp[2] << 8)
        ok = (result == a)
        print(f"{'PASS' if ok else 'FAIL'}[{i}] {v['name']}: val={val} raw=0x{a:04x} got=0x{result:04x}")
        if not ok: fails += 1
    port.close()
    print(f"\nResult: {len(vectors) - fails}/{len(vectors)} passed")
    return 0 if fails == 0 else 1

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Parameterized GF HW-conformance for AX7203")
    p.add_argument("--pack", type=Path, required=True)
    p.add_argument("--device", default="/dev/cu.usbserial-1120")
    p.add_argument("--baud", type=int, default=160000)
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()
    sys.exit(run(args.pack, args.device, args.baud, args.limit))
