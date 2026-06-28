#!/usr/bin/env python3
"""Cross-check: Python decode golden vs Corona RTL (iverilog dump) — 2-oracle."""
import sys
sys.path.insert(0, "conformance")
from corona_decode_host_ax7203 import golden

bad = n = 0
with open("/tmp/corona_fp8_posit8_dump.txt") as f:
    for line in f:
        fmt, code, out = map(int, line.split())
        n += 1
        g = golden(fmt, code)
        if out != g:
            bad += 1
            if bad <= 8:
                print(f"MISMATCH fmt={fmt} code={code} rtl=0x{out:08x} golden=0x{g:08x}")
print(f"cross-check: {n} pairs, {bad} mismatches (Python golden vs Corona RTL)")
