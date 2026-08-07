#!/usr/bin/env python3
"""Did fixing tekum_decode_param's loop bound change what it computes?

`pack_implicit_mant` looped to `pbits`, a runtime input. yosys rejects a
non-constant procedural for-loop bound outright, so the whole file could not be
read -- and with it tekum16_adder.v, which instantiates the module. iverilog
accepts it, which is exactly why the iverilog parse guard built in pass 237 never
saw this and audit_yosys_reads did.

The fix bounds the loop by the constant PAYLOAD_BITS and guards the body with
`if (k < pbits)`, the same idiom extract_C_u already uses ten lines above.

A fix that makes a file parse is worthless if it also changes the arithmetic. This
compares the two versions directly: the pre-fix module and the post-fix module are
instantiated side by side and driven with every code at four widths, and every
output is required to match -- sign, exponent, mantissa, implicit-bit index, all
three classification flags, and the FP32 view.

    N=8      256 codes
    N=12     4,096
    N=16     65,536      <- the width tekum16_adder instantiates
    N=20     1,048,576

Exhaustive at each, so there is no sampling to argue about.

The old version is read from git, not reconstructed by hand, because a
hand-written "before" that differs from the real one proves nothing.

Usage:  python3 research/witness_tekum_decode_equiv.py [--widths 8,12,16]
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REL = "fpga/openxc7-synth/tekum_decode_param.v"
OLD_LOOP = "k < pbits; k"           # what the pre-fix file contains
NEW_LOOP = "k < PAYLOAD_BITS; k"    # what the current file must contain


def find_prefix_revision():
    """The newest revision of REL, on any ref, that still has the old loop.

    Deliberately NOT a pinned SHA. This repo squash-merges, so the commit that
    made the change does not survive on main under its own hash, and a witness
    pinned to it would start reporting "cannot read the pre-fix version" the
    moment its branch was tidied up -- which reads like the witness broke rather
    than like the history moved.

    Returns None if no such revision is reachable. The caller must then refuse to
    run, not fabricate a "before": a hand-written pre-fix file that differs from
    the real one proves nothing, which is the entire point of this witness.
    """
    r = subprocess.run(["git", "log", "--all", "--format=%H", "--", REL],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    for sha in r.stdout.split():
        got = subprocess.run(["git", "show", "%s:%s" % (sha, REL)],
                             cwd=ROOT, capture_output=True, text=True)
        if got.returncode == 0 and OLD_LOOP in got.stdout:
            return sha, got.stdout
    return None

TB = r"""
`timescale 1ns/1ps
module tb_equiv;
    localparam integer N = %(n)d;
    reg  [N-1:0] code;
    wire s_o, s_n, z_o, z_n, nar_o, nar_n, f_o, f_n;
    wire signed [31:0] e_o, e_n;
    wire [N-1:0] m_o, m_n;
    wire [7:0] i_o, i_n;
    wire [31:0] fp_o, fp_n;
    tekum_decode_param_OLD #(.N(N)) u_old (.clk(1'b0), .rst_n(1'b1), .tekum_in(code),
        .sign_o(s_o), .exp_o(e_o), .mant_o(m_o), .mant_msb_idx_o(i_o),
        .is_nar_o(nar_o), .is_zero_o(z_o), .is_finite_o(f_o), .fp32_out(fp_o));
    tekum_decode_param_NEW #(.N(N)) u_new (.clk(1'b0), .rst_n(1'b1), .tekum_in(code),
        .sign_o(s_n), .exp_o(e_n), .mant_o(m_n), .mant_msb_idx_o(i_n),
        .is_nar_o(nar_n), .is_zero_o(z_n), .is_finite_o(f_n), .fp32_out(fp_n));
    integer c, bad, checked;
    initial begin
        bad = 0; checked = 0;
        for (c = 0; c < (1 << N); c = c + 1) begin
            code = c[N-1:0]; #1; checked = checked + 1;
            if (s_o !== s_n || e_o !== e_n || m_o !== m_n || i_o !== i_n ||
                nar_o !== nar_n || z_o !== z_n || f_o !== f_n || fp_o !== fp_n) begin
                bad = bad + 1;
                if (bad <= 5)
                    $display("MISMATCH code=%%04h mant %%04h/%%04h idx %%0d/%%0d fp %%08h/%%08h",
                             code, m_o, m_n, i_o, i_n, fp_o, fp_n);
            end
        end
        $display("EQUIV N=%%0d checked %%0d mismatches %%0d", N, checked, bad);
        $finish;
    end
endmodule
"""


def variant(src, suffix):
    return re.sub(r"\bmodule\s+tekum_decode_param\b",
                  "module tekum_decode_param_" + suffix, src, count=1)


def main():
    widths = [8, 12, 16, 20]
    if "--widths" in sys.argv:
        widths = [int(x) for x in sys.argv[sys.argv.index("--widths") + 1].split(",")]

    new_src = open(os.path.join(ROOT, REL), encoding="utf-8").read()
    if NEW_LOOP not in new_src:
        print("the current file does not contain the fixed loop -- nothing to witness.")
        return 2

    found = find_prefix_revision()
    if not found:
        print("no revision of %s reachable from any ref still contains the pre-fix" % REL)
        print("loop. Without a real 'before' there is nothing to compare, and this")
        print("witness will not guess one. Fetch the branch that carried the fix.")
        return 2
    sha, old_src = found
    print("pre-fix revision : %s" % sha[:12])
    print("post-fix         : working tree")
    print()

    total, bad_total = 0, 0
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "old.v"), "w").write(variant(old_src, "OLD"))
        open(os.path.join(d, "new.v"), "w").write(variant(new_src, "NEW"))
        for n in widths:
            tb = os.path.join(d, "tb_%d.v" % n)
            open(tb, "w").write(TB % {"n": n})
            exe = os.path.join(d, "eq_%d" % n)
            c = subprocess.run(["iverilog", "-g2012", "-o", exe, tb,
                                os.path.join(d, "old.v"), os.path.join(d, "new.v")],
                               capture_output=True, text=True)
            if c.returncode != 0:
                print("N=%-3d compile failed: %s" % (n, c.stderr.strip()[:100]))
                bad_total += 1
                continue
            out = subprocess.run([exe], capture_output=True, text=True, timeout=1800).stdout
            line = [x for x in out.splitlines() if x.startswith("EQUIV")]
            if not line:
                print("N=%-3d produced no verdict" % n)
                bad_total += 1
                continue
            m = re.search(r"checked (\d+) mismatches (\d+)", line[0])
            checked, bad = int(m.group(1)), int(m.group(2))
            total += checked
            bad_total += bad
            print("N=%-3d %9d codes   mismatches %d" % (n, checked, bad))
            for ln in out.splitlines():
                if ln.startswith("MISMATCH"):
                    print("      %s" % ln)

    print()
    print("codes compared, pre-fix against post-fix : %d" % total)
    print("outputs that differ                      : %d" % bad_total)
    if not bad_total:
        print("the fix changed what yosys accepts and nothing else.")
    return 1 if bad_total else 0


if __name__ == "__main__":
    sys.exit(main())
