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

def golden_flushes_subnormals(modname):
    """Static check: does the golden SOURCE flush subnormals to zero?
    Reads the conformance .py and greps for the flush pattern
    ('exp.*< 1 -> return sign-shifted-zero'). If yes, the format is CLEAN
    by definition (HW matches golden; see FINDING_2026_07_03_catalog retraction)."""
    import os, re
    path = os.path.join("conformance", modname + ".py")
    if not os.path.exists(path):
        return None  # unknown
    with open(path) as f:
        src = f.read()
    # common flush patterns in the goldens
    if re.search(r"exp_final\s*<\s*1\b.*return|exp\s*<\s*1'sd1|<\s*-?149\b.*return.*0|return\s+sign\s*<<\s*31", src):
        return True
    return False

print(f"{'format':<14} {'N':>4} {'golden?':>7} {'golden-flush?':>14} {'sub-prod':>9} {'verdict':>34}")
print("-" * 92)
rnd = random.Random(2026)
results = []
for fmt, modname, N in CANDIDATES:
    try:
        m = importlib.import_module(modname)
        g = find_golden(m)
        if g is None:
            print(f"{fmt:<14} {N:>4} {'no':>7} {'-':>14} {'-':>9} {'SKIP (no golden)':>34}")
            continue
        # golden-side static check: does the golden definition itself flush?
        gflush = golden_flushes_subnormals(modname)
        # sample across the format's range (biased toward small-magnitude for subnormal hunting)
        sample = [rnd.getrandbits(N) for _ in range(3000)]
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
        # COMBINED verdict (the lesson from the ibm_hfp32 retraction):
        #   affected ONLY if golden produces subnormals (sampled > 0) AND golden
        #   does NOT itself flush (else HW matches golden -> CLEAN by definition).
        if gflush:
            verdict = "CLEAN (golden flushes -> HW matches)"
        elif sub_count > 0:
            verdict = "*** AFFECTED -- check HW flush ***"
        else:
            verdict = "inconclusive (sampling gap; golden keeps subnormals)"
        gf_str = "yes" if gflush else ("no" if gflush is False else "?")
        print(f"{fmt:<14} {N:>4} {'yes':>7} {gf_str:>14} {sub_count:>9} {verdict:>34}")
        results.append((fmt, sub_count, gflush))
    except ImportError as e:
        print(f"{fmt:<14} {N:>4} {'err':>7} {'-':>14} {'-':>9} {'no module':>34}")

print("\n== PRIORITY for subnormal-fix loops (true bugs only) ==")
# truly affected = golden keeps subnormals (gflush is False) AND sampling found some
true_aff = [(f, c) for f, c, gf in results if gf is False and c > 0]
true_aff.sort(key=lambda x: -x[1])
if not true_aff:
    print("  (none found -- all formats either flush by convention or sampling-gap)")
else:
    for f, c in true_aff:
        print(f"  {f:<14} {c} subnormal-producing inputs, golden does NOT flush -> check HW (fix mirrors lns16 bffc7a2ab)")
