#!/usr/bin/env python3
"""Verify the TX-race fix: for each sample, compile BOTH the original (.bak)
and the fixed (.v) with identical, per-wrapper dependencies, then diff the
error sets. The fix is correct iff it introduces NO new errors (and ideally
removes the tx_shift race).

Usage: verify_tx_fix.py <file1.v> [file2.v ...]
"""
import subprocess, re, sys, os, glob

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(REPO, "fpga", "openxc7-synth")
STARTUP = "/tmp/startup_stub.v"

# All available compute cores + the DSP mock (only included if needed).
CORES = {
    "gf_adder_param": "gf_adder_param.v",
    "gf_mul_param": "gf_mul_param.v",
    "gf_mul_dsp_param": "gf_mul_dsp_param.v",
    "gf_div_param": "gf_div_param.v",
    "gf_sqrt_param": "gf_sqrt_param.v",
    "gf_quire_param": "gf_quire_param.v",
    "gf_decode_param": "gf_decode_param.v",
    "gf_wide_decode": "gf_wide_decode.v",
}

def _abs(fn):
    if os.path.isabs(fn):
        return fn
    return os.path.join(DIR, fn)

def deps_for(path):
    text = open(path).read()
    d = [STARTUP]
    for mod, fn in CORES.items():
        if re.search(r"\b" + mod + r"\s*#", text):
            d.append(_abs(fn))
            if mod == "gf_mul_dsp_param":
                d.append(_abs("DSP48E1_mock.v"))
    return d

def compile_count(path):
    deps = deps_for(path)
    p = subprocess.run(
        ["iverilog", "-g2012", "-o", "/dev/null", path] + deps,
        capture_output=True, text=True,
    )
    # Collect actual error lines (skip count footers / "missing modules"
    # summary banners, which vary by total count and aren't specific errors).
    errs = []
    for line in (p.stdout + p.stderr).splitlines():
        line = re.sub(r"\S*\.(v\.bak|bak|v):\d+:", "FILE:", line)
        if "error" not in line.lower():
            continue
        if re.match(r"\s*\d+ error\(s\) during", line):
            continue
        if line.strip().startswith("***"):
            continue
        errs.append(line.strip())
    return p.returncode, errs

def main():
    files = sys.argv[1:]
    if not files:
        # default: 5 random fixed files
        baks = sorted(glob.glob(os.path.join(DIR, "corona_compute_*.bak")))
        import random
        files = [b[:-4] for b in random.sample(baks, min(5, len(baks)))]
    # resolve bare filenames to absolute paths in the synth dir
    files = [f if os.path.isabs(f) or os.path.dirname(f) else _abs(f) for f in files]
    print("Verifying {} files (compare .bak original vs fixed .v)".format(len(files)))
    print("=" * 70)
    all_ok = True
    for vpath in files:
        base = os.path.basename(vpath)
        bak = vpath + ".bak"
        if not os.path.exists(bak):
            print("  {} : NO .bak, skip".format(base)); continue
        rc_b, err_b = compile_count(bak)
        rc_v, err_v = compile_count(vpath)
        set_b = set(err_b); set_v = set(err_v)
        new = set_v - set_b          # errors introduced by the fix
        gone = set_b - set_v         # errors removed by the fix
        status = "CLEAN" if rc_v == 0 else ("OK(no new errs)" if not new else "NEW ERRORS")
        if new:
            all_ok = False
        print("  {} : {}".format(base, status))
        print("      .bak rc={} errs={} | .v rc={} errs={} | new={} gone={}".format(
            rc_b, len(err_b), rc_v, len(err_v), len(new), len(gone)))
        if new:
            for e in sorted(new)[:8]:
                print("        NEW: " + e)
    print("=" * 70)
    print("RESULT:", "ALL CLEAN / NO REGRESSIONS" if all_ok else "REGRESSIONS FOUND")
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
