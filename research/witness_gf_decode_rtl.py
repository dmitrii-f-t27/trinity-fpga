#!/usr/bin/env python3
"""Run gf_decode_param under iverilog and hold it to the exact golden.

One iverilog invocation per code is unusable -- gf16 alone is 65,536 of them --
so this emits a single testbench per format that loops over the whole code list
and prints one line each, then compares every line against
conformance/gf_decode_golden.decode_to_fp32, which agrees with gf_ref.decode on
all 1,135,952 codes of gf4 through gf20.

Narrow formats are checked EXHAUSTIVELY. Wide ones get the structural sample
(single-bit and single-hole codes, the interesting exponents, a fixed-seed tail),
because that is where pass 234's defects lived.

This exists because pass 238 changed two things in the exponent datapath -- the
working width, and the declaration of BIAS -- and a change to a module that gf16's
Tier-E evidence rests on has to be shown not to move gf16.

Usage:  python3 research/witness_gf_decode_rtl.py [format ...]
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")
CORE = os.path.join(ROOT, "fpga", "openxc7-synth", "gf_decode_param.v")
sys.path.insert(0, CONF)
sys.path.insert(0, HERE)

import gf_ref                                        # noqa: E402
from gf_decode_golden import decode_to_fp32          # noqa: E402
from audit_host_structural import structural_codes   # noqa: E402

EXHAUSTIVE_MAX = 16          # widths at or below this are checked on every code
HAS_INF = {"gf16"}


def emit_tb(N, E, M, BIAS, codes, has_inf):
    lines = "\n".join(
        "        gf_in = %d'h%0*x; #1 $display(\"%%h\", fp32_out);" % (N, (N + 3) // 4, c)
        for c in codes)
    return f"""`timescale 1ns / 1ps
module tb;
    reg [{N-1}:0] gf_in;
    wire [31:0] fp32_out;
    gf_decode_param #(.N({N}), .E({E}), .M({M}), .BIAS({BIAS}),
                      .HAS_INF({1 if has_inf else 0}), .OUT_REG(0)) u_dec (
        .gf_in(gf_in), .fp32_out(fp32_out),
        .is_nan_o(), .is_inf_o(), .is_zero_o(), .is_subnormal_o());
    initial begin
{lines}
        $finish;
    end
endmodule
"""


def run(fmt_name, fmt):
    E, M, B = fmt.exp_bits, fmt.mant_bits, fmt.bias
    N = 1 + E + M
    if N <= EXHAUSTIVE_MAX:
        codes = list(range(1 << N))
        how = "exhaustive"
    else:
        codes = structural_codes(N, fmt)
        how = "structural"
    with tempfile.TemporaryDirectory() as td:
        tb = os.path.join(td, "tb.v")
        with open(tb, "w") as fh:
            fh.write(emit_tb(N, E, M, B, codes, fmt_name in HAS_INF))
        vvp = os.path.join(td, "tb.vvp")
        c = subprocess.run(["iverilog", "-o", vvp, tb, CORE],
                           capture_output=True, text=True)
        if c.returncode != 0:
            return fmt_name, N, how, 0, -1, (c.stderr or c.stdout).strip()[:160]
        r = subprocess.run(["vvp", vvp], capture_output=True, text=True)
        # Keep only the result lines. iverilog's "$finish called at ..." notice is
        # prefixed with the testbench PATH, so a startswith("$finish") filter
        # misses it -- which is how the first run reported "17 lines for 16 codes"
        # on every format.
        out = [ln.strip() for ln in r.stdout.splitlines()
               if len(ln.strip()) == 8 and all(c in "0123456789abcdefABCDEF"
                                               for c in ln.strip())]
    if len(out) != len(codes):
        return fmt_name, N, how, 0, -1, "got %d lines for %d codes" % (len(out), len(codes))
    bad = 0
    first = ""
    for code, line in zip(codes, out):
        rtl = int(line, 16)
        exact = decode_to_fp32(code, N, E, M, B, fmt_name)
        if rtl != exact:
            bad += 1
            if not first:
                first = "code %#x rtl=%#010x exact=%#010x" % (code, rtl, exact)
    return fmt_name, N, how, len(codes), bad, first


def main():
    want = [a for a in sys.argv[1:] if not a.startswith("-")]
    names = want or sorted(gf_ref.FORMATS, key=lambda k: gf_ref.FORMATS[k].exp_bits)
    print("%-8s %5s %-11s %9s %7s" % ("format", "bits", "how", "codes", "differ"))
    total = totbad = fails = 0
    for name in names:
        fmt = gf_ref.FORMATS.get(name)
        if fmt is None:
            print("%-8s unknown format" % name)
            fails += 1
            continue
        n, bits, how, count, bad, first = run(name, fmt)
        if bad < 0:
            print("%-8s %5d %-11s %9s %7s  %s" % (n, bits, how, "-", "ERR", first))
            fails += 1
            continue
        total += count
        totbad += bad
        print("%-8s %5d %-11s %9d %7d%s" % (n, bits, how, count, bad,
                                            "  <<<" if bad else ""))
        if first:
            print("         first: %s" % first)
    print()
    print("codes witnessed : %d" % total)
    print("disagreements   : %d" % totbad)
    print("formats errored : %d" % fails)
    return 1 if (totbad or fails) else 0


if __name__ == "__main__":
    sys.exit(main())
