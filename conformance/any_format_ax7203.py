#!/usr/bin/env python3
"""Universal encoding conformance harness for AX7203 — works with ANY t27 pack.
Reads raw bits from vectors, sends through UART identity-echo, checks round-trip.
Handles both GF pack schema (format_spec + test_vectors[].expected.raw)
and non-GF pack schema (vectors[].format_bits_int)."""
import argparse, json, serial, time, sys
from pathlib import Path

def extract_vectors(pack):
    """Extract (name, raw_int) pairs from any pack schema."""
    vectors = pack.get("test_vectors", pack.get("vectors", []))
    fmt = pack.get("format", pack.get("format_name", "?"))
    results = []
    for v in vectors:
        name = v.get("name", v.get("description", "?"))
        # Try any key ending in _bits_int (format-specific naming)
        raw = None
        for key in sorted(v.keys()):
            if key.endswith("_bits_int"):
                raw = int(v[key])
                break
        if raw is None:
            for key in ["raw", "expected_raw", "raw_int", "bits"]:
                if key in v and isinstance(v[key], (int, float)):
                    raw = int(v[key]); break
        if raw is None:
            # Try *_bits_hex
            for key in sorted(v.keys()):
                if key.endswith("_bits_hex"):
                    raw = int(v[key], 16); break
        if raw is None:
            # Try hex field directly
            if "hex" in v and isinstance(v["hex"], str):
                try: raw = int(v["hex"], 16)
                except: pass
        if raw is None:
            # Try expected.raw (GF schema)
            exp = v.get("expected", {})
            if isinstance(exp, dict) and "raw" in exp:
                raw = int(exp["raw"])
        if raw is not None:
            results.append((name, raw))
    return fmt, results

def run(pack_path, device, baud, limit):
    with open(pack_path) as f:
        pack = json.load(f)
    fmt, vectors = extract_vectors(pack)
    if limit: vectors = vectors[:limit]
    if not vectors:
        print(f"NO EXTRACTABLE VECTORS in {pack_path}")
        return 1

    port = serial.Serial(device, baud, timeout=2)
    fails = 0
    for i, (name, raw) in enumerate(vectors):
        a_lo = raw & 0xFF
        a_hi = (raw >> 8) & 0xFF
        frame = bytes([0xAA, 0x55, a_lo, a_hi, 0, 0, 0])
        port.reset_input_buffer()
        port.write(frame); port.flush()
        time.sleep(0.05)
        resp = port.read(4)
        if len(resp) >= 4:
            hw = resp[1] | (resp[2] << 8)
            ok = (hw == raw)
            tag = "PASS" if ok else f"FAIL hw=0x{hw:04x}"
            if not ok: fails += 1
            print(f"{'PASS' if ok else 'FAIL'}[{i}] {name}: raw=0x{raw:04x} {'' if ok else f'hw=0x{hw:04x}'}")
        else:
            print(f"FAIL[{i}] {name}: short response ({len(resp)}B)")
            fails += 1
    port.close()
    print(f"\nResult: {len(vectors)-fails}/{len(vectors)} passed [{fmt}]")
    return 0 if fails == 0 else 1

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--pack", type=Path, required=True)
    p.add_argument("--device", default="/dev/cu.usbserial-120")
    p.add_argument("--baud", type=int, default=160000)
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()
    sys.exit(run(args.pack, args.device, args.baud, args.limit))
