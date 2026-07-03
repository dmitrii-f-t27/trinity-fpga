#!/usr/bin/env python3
"""fpga_subnormal_audit — catalog-wide scan for the FP32 subnormal-flush bug class.

For each FP32-producing decoder with a conformance golden, samples inputs across
the format's range and checks: (a) does the golden produce FP32 subnormals
(exp_field=0, mantissa!=0) for any input? (b) if so, flag the decoder as having
the latent subnormal class (the HW flush-to-zero, if present, mismatches there).

This extends the lns16 finding (commit bffc7a2ab) across the catalog and guides
the next correctness-fix loops. Output: a table of formats + subnormal-producing
input counts + fix priority."""
import sys, importlib, random
sys.path.insert(0, "conformance")

# formats with a conformance golden + FP32 output
CANDIDATES = [
    ("binary64",        "binary64_decode_conformance_ax7203",        64),
    ("binary128",       "binary128_decode_conformance_ax7203",      128),
    ("ibm_hfp32",       "ibm_hfp32_decode_conformance_ax7203",       32),
    ("ibm_hfp64",       "ibm_hfp64_decode_conformance_ax7203",       64),
    ("vax_d",           "vax_d_decode_conformance_ax7203",           64),
    ("vax_g",           "vax_g_decode_conformance_ax7203",           64),
    ("ms_mbf32",        "ms_mbf32_decode_conformance_ax7203",        32),
    ("ms_mbf64",        "ms_mbf64_decode_conformance_ax7203",        64),
    ("posit32",         "posit32_decode_conformance_ax7203",         32),
    ("binary32",        "binary32_decode_conformance_ax7203",        32),
    ("decimal64",       "decimal64_decode_conformance_ax7203",       64),
    ("decimal128",      "decimal128_decode_conformance_ax7203",     128),
]

def find_golden(module):
    for name in dir(module):
        if name.startswith("golden_"):
            return getattr(module, name)
    return None

print(f"{'format':<14} {'N':>4} {'golden?':>7} {'sampled':>8} {'subnormal-prod':>16} {'status':>22}")
print("-" * 78)
rnd = random.Random(2026)
results = []
for fmt, modname, N in CANDIDATES:
    try:
        m = importlib.import_module(modname)
        g = find_golden(m)
        if g is None:
            print(f"{fmt:<14} {N:>4} {'no':>7} {'-':>8} {'-':>16} {'SKIP (no golden)':>22}")
            continue
        # sample across the format's range (biased toward small-magnitude for subnormal hunting)
        sample = [rnd.getrandbits(N) for _ in range(3000)]
        # add small-magnitude codes (likely to produce small FP32 values)
        sample += list(range(0, 512))
        if N >= 64:
            sample += [0x0010_0000_0000_0000 + i for i in range(0, 512)]
        sub_count = 0
        checked = 0
        for code in sample:
            try:
                fp = g(code)
            except Exception:
                continue
            checked += 1
            exp_field = (fp >> 23) & 0xFF
            mant = fp & 0x7FFFFF
            if exp_field == 0 and mant != 0:
                sub_count += 1
        status = "AFFECTED (has subnormal class)" if sub_count > 0 else "clean (no subnormals in range)"
        print(f"{fmt:<14} {N:>4} {'yes':>7} {checked:>8} {sub_count:>16} {status:>22}")
        results.append((fmt, sub_count))
    except ImportError as e:
        print(f"{fmt:<14} {N:>4} {'err':>7} {'-':>8} {'-':>16} {'no module':>22}")

print("\n== PRIORITY for subnormal-fix loops ==")
affected = [(f, c) for f, c in results if c > 0]
affected.sort(key=lambda x: -x[1])
if not affected:
    print("  (none found -- all clean)")
else:
    for f, c in affected:
        print(f"  {f:<14} {c} subnormal-producing inputs in sample (fix mirrors lns16 commit bffc7a2ab)")
