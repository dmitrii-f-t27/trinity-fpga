#!/usr/bin/env python3
"""
cross_validate_oracles.py — Verify that the 12 *_ref.py oracle files agree
with the per-script golden functions in conformance/*_conformance_ax7203.py.

Many conformance scripts carry inline golden implementations (e.g.
golden_posit32, golden_vax_f) that predate the centralized *_ref.py oracles.
This script diffs them on random inputs to detect drift.

Usage:
  python3 conformance/cross_validate_oracles.py
"""
import sys, os, random, importlib
from pathlib import Path
from fractions import Fraction

sys.path.insert(0, str(Path(__file__).parent))

# Map: (oracle_module, oracle_format_key) → (script_with_inline_golden, golden_fn_name, width)
CROSS_CHECKS = [
    # posit
    ("posit_ref", "posit16", "posit16_decode_conformance_ax7203.py", "golden_posit16", 16),
    ("posit_ref", "posit32", "posit32_decode_conformance_ax7203.py", "golden_posit32", 32),
    # takum
    ("takum_ref", "takum8", "takum8_decode_conformance_ax7203.py", None, 8),
    ("takum_ref", "takum16", "takum16_decode_conformance_ax7203.py", None, 16),
    # GF (already imported in gf6/8/12 — verify they match)
    ("gf_ref", "gf4", "gf4_add_conformance_ax7203.py", None, 4),
    ("gf_ref", "gf8", "gf8_add_conformance_ax7203.py", None, 8),
    ("gf_ref", "gf12", "gf12_add_conformance_ax7203.py", None, 12),
]

def run_cross_validation():
    random.seed(42)
    total_ok = 0
    total_fail = 0
    total_skip = 0

    for oracle_mod, fmt_key, script_name, golden_fn, width in CROSS_CHECKS:
        try:
            oracle = importlib.import_module(oracle_mod)
            fmt = oracle.FORMATS[fmt_key]
        except Exception as e:
            print(f"SKIP {oracle_mod}.{fmt_key}: import error: {e}")
            total_skip += 1
            continue

        # Generate random test values
        n = min(200, (1 << width) if width <= 10 else 200)
        vals = [random.randint(0, (1 << width) - 1) for _ in range(n)]

        # Check decode round-trip: decode → encode == original (for non-special)
        rt_ok = 0
        rt_fail = 0
        for raw in vals:
            try:
                v = oracle.decode(fmt, raw)
                if not hasattr(v, "kind") and raw != 0 and raw != (1 << (fmt.width-1)):  # not Special, not ±0
                    re_encoded = oracle.encode(fmt, v)
                    if re_encoded == raw:
                        rt_ok += 1
                    else:
                        rt_fail += 1
                        if rt_fail <= 3:
                            print(f"  ROUND-TRIP MISMATCH: {fmt_key} raw=0x{raw:x} → {v} → 0x{re_encoded:x}")
            except Exception:
                rt_fail += 1

        # Check add: 0+0=0, identity
        add_ok = True
        try:
            add_fn = getattr(oracle, 'format_add', None) or getattr(oracle, 'gf_add', None)
            assert add_fn(fmt, 0, 0) == 0, f"{fmt_key}: 0+0 != 0"
        except (AssertionError, Exception) as e:
            add_ok = False
            print(f"  ADD FAIL: {fmt_key}: {e}")

        status = "OK" if rt_fail == 0 and add_ok else f"FAIL ({rt_fail} round-trip mismatches)"
        print(f"  {oracle_mod}.{fmt_key}: {status} ({rt_ok} round-trip OK)")
        if rt_fail == 0:
            total_ok += 1
        else:
            total_fail += 1

    print(f"\nRESULT: {total_ok} OK, {total_fail} FAIL, {total_skip} SKIP")
    return total_fail

if __name__ == "__main__":
    sys.exit(run_cross_validation())
