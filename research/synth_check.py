#!/usr/bin/env python3
"""Does the RTL still SYNTHESISE, and did the recent changes move the narrow cases?

Passes 237 through 243 changed 4,776 sites of RTL plus the decoder's parameter
declarations, and every check behind them was iverilog. iverilog elaborates; it
does not synthesise. Until yosys has seen it, "fixed" means "fixed in simulation".

Two things are asked here:

  SYNTH      each subject builds under `synth_xilinx -flatten -nodsp`. The -nodsp
             is not optional -- the repo's own note records that DSP48E1 inference
             on the GF multiplier turns into a routing failure.
  UNCHANGED  gf_decode_param at the narrow widths -- the ones the Tier-E evidence
             actually rests on -- produces the same cell counts before and after
             pass 238. That pass widened EXP_CALC_W and redeclared BIAS, with a
             floor chosen so narrow instantiations stay bit-identical. This is
             where that claim gets tested against a synthesiser rather than
             asserted.

nextpnr-xilinx is not installed here, so place-and-route is out of scope. The
half that the changes actually risk is elaboration and synthesis.

Usage:  python3 research/synth_check.py [--verbose]
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SYNTH = os.path.join(ROOT, "fpga", "openxc7-synth")

# The pass that changed the decoder core; its parent is the "before".
BEFORE_REF = "331f6be24^:fpga/openxc7-synth/gf_decode_param.v"

# (name, N, E, M, BIAS, HAS_INF)
DECODER_CASES = [
    ("gf4", 4, 1, 2, 0, 0),
    ("gf8", 8, 3, 4, 3, 0),
    ("gf16", 16, 6, 9, 31, 1),
    ("gf24", 24, 9, 14, 255, 0),
    ("gf32", 32, 12, 19, 2047, 0),
]

# yosys 0.63's `stat` prints a per-cell-type table and no single total line, so
# the metric here is the LUT count -- summed across LUT1..LUT6. That is the number
# a synthesis regression would move, and it does not depend on how buffers and
# I/O cells happen to be counted.
LUTS = re.compile(r"^\s+(\d+)\s+LUT[1-6]\s*$", re.M)


def yosys(script):
    r = subprocess.run(["yosys", "-p", script], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def cell_count(path, top, params=None):
    p = ""
    if params:
        p = "chparam " + " ".join("-set %s %s" % kv for kv in params) + " %s; " % top
    rc, out = yosys("read_verilog %s; %shierarchy -top %s; synth_xilinx -flatten -nodsp; stat"
                    % (path, p, top))
    if rc != 0:
        first = next((l for l in out.splitlines() if "ERROR" in l), out.strip()[:150])
        return None, first
    got = LUTS.findall(out)
    if not got:
        return None, "synthesised but no LUTs in stat"
    # the table is printed twice (once per `stat`); take the last full set
    half = len(got) // 2 or len(got)
    return sum(int(x) for x in got[-half:]), ""


def decoder_before_after():
    with tempfile.TemporaryDirectory() as td:
        old = os.path.join(td, "old.v")
        r = subprocess.run(["git", "show", BEFORE_REF], cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode != 0:
            return [("(before) unavailable", None, None, r.stderr.strip()[:120])]
        with open(old, "w") as fh:
            fh.write(r.stdout)
        new = os.path.join(SYNTH, "gf_decode_param.v")
        rows = []
        for name, N, E, M, B, HI in DECODER_CASES:
            params = [("N", N), ("E", E), ("M", M), ("BIAS", B), ("HAS_INF", HI)]
            a, ea = cell_count(old, "gf_decode_param", params)
            b, eb = cell_count(new, "gf_decode_param", params)
            rows.append((name, a, b, ea or eb))
        return rows


def subjects():
    """Wrappers touched by passes 237-243, one per class of change."""
    return [
        ("corona_decode_gf24_ax7203.v", "pass 237 repaired its spliced .HAS_INF(0)"),
        ("corona_decode_gf256_ax7203.v", "pass 237, same splice"),
        ("corona_decode_mxgf4_ax7203.v", "pass 237 gave it HAS_INF(0)"),
        ("corona_compute_binary128_add_ax7203.v", "pass 241 saturation + 242 zero sign"),
        ("corona_compute_cray_float_add_ax7203.v", "pass 241 saturation"),
        ("corona_compute_ibm_hfp32_add_ax7203.v", "pass 243 result-packing sign"),
        ("corona_compute_decimal32_add_ax7203.v", "pass 242 sign hardcoded to zero"),
        ("corona_compute_afp_add_ax7203.v", "pass 242 zero sign, narrowing side"),
    ]


def main():
    verbose = "--verbose" in sys.argv
    print("UNCHANGED -- gf_decode_param cell count before and after pass 238")
    print("%-8s %10s %10s %s" % ("width", "before", "after", ""))
    moved = 0
    for name, a, b, err in decoder_before_after():
        flag = ""
        if a is None or b is None:
            flag = "  ERROR: %s" % err
            moved += 1
        elif a != b:
            flag = "  <<< MOVED"
            moved += 1
        print("%-8s %10s %10s%s" % (name, a, b, flag))
    print()

    print("SYNTH -- wrappers touched by passes 237-243")
    fails = 0
    core = os.path.join(SYNTH, "gf_decode_param.v")
    adder = os.path.join(SYNTH, "gf_adder_param.v")
    for base, why in subjects():
        path = os.path.join(SYNTH, base)
        if not os.path.exists(path):
            print("%-44s MISSING" % base[:44])
            fails += 1
            continue
        top = base[:-2]
        rc, out = yosys("read_verilog %s %s %s; hierarchy -top %s; "
                        "synth_xilinx -flatten -nodsp; stat" % (path, core, adder, top))
        got = LUTS.findall(out)
        if rc != 0:
            first = next((l for l in out.splitlines() if "ERROR" in l), "")
            print("%-44s FAIL  %s" % (base[:44], first.strip()[:70]))
            fails += 1
        else:
            half = len(got) // 2 or len(got)
            n = sum(int(x) for x in got[-half:]) if got else "?"
            print("%-44s ok    %6s LUTs   (%s)" % (base[:44], n, why))
    print()
    print("cases where the narrow decoder moved : %d" % moved)
    print("wrappers that failed to synthesise   : %d" % fails)
    print("place-and-route is out of scope here -- nextpnr-xilinx is not installed.")
    return 1 if (moved or fails) else 0


if __name__ == "__main__":
    sys.exit(main())
