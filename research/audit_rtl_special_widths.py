#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Does the synthesized GF decoder agree with the spec about which widths have infinities?

Pass 197 settled the question from the spec side. `t27/specs/numeric/gf8.t27` defines
`exp_max = (1 << EXP_BITS) - 1 - EXP_BIAS`, so the all-ones exponent field carries finite
values and nothing is reserved for Inf or NaN. Only `gf16.t27` declares them, with
`GF16_INF_POS 0x7E00` and friends.

`fpga/openxc7-synth/gf_decode_param_pipe.v` does not know that. Lines 61 and 62:

    wire cls_inf0 = is_exp_max0 &&  is_mant_zero0;
    wire cls_nan0 = is_exp_max0 && !is_mant_zero0;

Unconditional. The module has parameters for N, E, M and BIAS and none for whether the
format has infinities, so every width it is instantiated at classifies the all-ones
exponent as special.

This file runs the RTL rather than reading it, because a code reading is an argument and a
simulation is a measurement. Requires iverilog.

    python3 research/audit_rtl_special_widths.py [--verbose] [--self-check]

WHAT IT FOUND, GRADED BY SEVERITY
---------------------------------
    gf16    RTL says +Inf, spec says +Inf                        correct
    gf8     RTL gives 0x7F800000, spec requires 0x41800000       WRONG NUMBER
    gf24    RTL gives 0x7F800000, spec value 1.16e77             flag only
    gf32    RTL gives 0x7F800000, spec value 3.23e13...          flag only

gf8 is the case that matters most and it is worth being precise about why. Its largest
finite value is 16, which fp32 represents exactly, so the disagreement is visible in the
converted number: the hardware returns an infinity where the format has a number. At gf24
and gf32 the correct finite value overflows fp32 anyway, so `fp32_out` is `0x7F800000`
either way and only `is_inf_o` disagrees. Reporting those three as one defect would
overstate two of them.
"""
from __future__ import annotations

import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RTL = os.path.join(ROOT, "fpga", "openxc7-synth", "gf_decode_param_pipe.v")

TB = """`timescale 1ns/1ps
module tb_special;
  parameter N=%d, E=%d, M=%d, BIAS=%d;
  reg clk=0, rst_n=0;
  reg [N-1:0] gf_in;
  wire [31:0] fp32_out; wire is_nan_o,is_inf_o,is_zero_o,is_subnormal_o;
  gf_decode_param_pipe #(.N(N),.E(E),.M(M),.BIAS(BIAS)) dut(
    .clk(clk),.rst_n(rst_n),.gf_in(gf_in),.fp32_out(fp32_out),
    .is_nan_o(is_nan_o),.is_inf_o(is_inf_o),
    .is_zero_o(is_zero_o),.is_subnormal_o(is_subnormal_o));
  always #5 clk=~clk;
  initial begin
    #12 rst_n=1;
    gf_in = {1'b0, {E{1'b1}}, {M{1'b0}}};
    #40 $display("RESULT %%h %%b %%b", fp32_out, is_inf_o, is_nan_o);
    $finish;
  end
endmodule
"""


def have_iverilog():
    return subprocess.run(["which", "iverilog"], capture_output=True).returncode == 0


def run_rtl(n, e, m, b):
    """(fp32_out, is_inf, is_nan) from a real simulation, or None."""
    with tempfile.TemporaryDirectory() as d:
        tb = os.path.join(d, "tb.v")
        vvp = os.path.join(d, "tb.vvp")
        open(tb, "w").write(TB % (n, e, m, b))
        r = subprocess.run(["iverilog", "-g2012", "-o", vvp, tb, RTL],
                           capture_output=True, text=True)
        if r.returncode:
            return None
        out = subprocess.run(["vvp", vvp], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.startswith("RESULT"):
            _, fp, inf, nan = line.split()
            return int(fp, 16), inf == "1", nan == "1"
    return None


def spec_fp32(gf, name):
    """What fp32 the spec's value converts to, and whether it is finite."""
    f = gf.FORMATS[name]
    top = ((1 << f.exp_bits) - 1) << f.mant_bits
    v = gf.decode(f, top)
    if isinstance(v, gf.Special):
        return None, "special"
    try:
        return struct.unpack(">I", struct.pack(">f", float(v)))[0], "finite"
    except OverflowError:
        return 0x7F800000, "finite, overflows fp32"


def main() -> int:
    verbose = "--verbose" in sys.argv
    if not have_iverilog():
        print("iverilog not found.")
        print("SKIPPED -- not a pass. This check measures the RTL; it cannot infer it.")
        return 2
    if not os.path.exists(RTL):
        print(f"{RTL} absent.\nSKIPPED -- not a pass.")
        return 2

    sys.path.insert(0, os.path.join(ROOT, "conformance"))
    import importlib
    gf = importlib.import_module("gf_ref")

    wrong_number, flag_only, agree = [], [], []
    print(f"  {'width':<7}{'RTL fp32':>12}{'is_inf':>8}   {'spec fp32':>12}  verdict")
    for name in ("gf8", "gf16", "gf24", "gf32"):
        f = gf.FORMATS[name]
        got = run_rtl(f.width, f.exp_bits, f.mant_bits, f.bias)
        if got is None:
            print(f"  {name:<7} simulation failed -- not counted either way")
            continue
        fp32, is_inf, is_nan = got
        want, kind = spec_fp32(gf, name)
        if kind == "special":
            verdict = "correct -- the spec declares Inf here"
            agree.append(name)
        elif want != fp32:
            verdict = "WRONG NUMBER"
            wrong_number.append((name, fp32, want))
        else:
            verdict = "flag only (the finite value overflows fp32)"
            flag_only.append(name)
        w = "n/a" if want is None else f"{want:#010x}"
        print(f"  {name:<7}{fp32:>#12x}{int(is_inf):>8}   {w:>12}  {verdict}")

    print(f"\n  widths where the RTL returns a wrong NUMBER : {len(wrong_number)}")
    print(f"  widths where only the flag disagrees        : {len(flag_only)}")
    print(f"  widths where the RTL is correct             : {len(agree)}")

    inv = wrapper_inventory()
    wrong = [r for r in inv if r[2] is False]
    print(f"\n  board decode wrappers instantiating gf_decode_param : {len(inv)}")
    print(f"    at a width the spec gives no infinities            : {len(wrong)}")
    for name, n, hi in inv:
        print(f"      {name:<38} N={n:<5} spec has_inf={hi}")

    print("""
The project already knows the answer. gf_adder_param carries a HAS_INF parameter,
documented with the same spec lines gf_ref cites (gf8.t27:115-119), and the gf8 compute
wrapper instantiates it with HAS_INF(0). gf_decode_param has N, E, M, BIAS and OUT_REG
and no such parameter. The knowledge was applied to the adder and never to the decoder,
which is why the compute cells are right and the decode cells are not.

The Tier-E chains for gf8 are compute cells -- add, mul and sub -- and they use
gf_adder_param with the correct flag. No published Tier-E claim is invalidated by this.

The module classifies the all-ones exponent as Inf or NaN with no parameter for whether
the format has them, so this is one line of RTL behaving four different ways depending on
what the spec says about the width it was instantiated at.

Grading matters here. At gf8 the largest finite value is 16, which fp32 holds exactly, so
the hardware returns an infinity where the format has a number and the difference is
visible in fp32_out. At gf24 and gf32 the correct finite value overflows fp32 anyway, so
only is_inf_o disagrees. Calling all three the same defect would overstate two of them.

Not fixed here: the RTL belongs to the synthesis line.""")
    return 1 if wrong_number else 0


def wrapper_inventory():
    """Which board wrappers instantiate the parameterless decoder at a finite-max width.

    The point of listing them is that the project already knows the answer. Its sibling
    module gf_adder_param carries

        parameter HAS_INF = 0,   // gf8.t27:115-119 -- exp=all-ones is a FINITE max_value

    citing the same spec lines gf_ref cites, and the gf8 compute wrapper instantiates it
    with HAS_INF(0). The knowledge was applied to the adder and never to the decoder.
    """
    import glob
    import importlib
    import re
    sys.path.insert(0, os.path.join(ROOT, "conformance"))
    gf = importlib.import_module("gf_ref")
    out = []
    for path in sorted(glob.glob(os.path.join(
            ROOT, "fpga", "openxc7-synth", "corona_decode_gf*_ax7203.v"))):
        text = open(path, encoding="utf-8", errors="replace").read()
        m = re.search(r"gf_decode_param\s*#\(\s*\.N\((\d+)\)", text)
        if not m:
            continue
        n = int(m.group(1))
        name = f"gf{n}"
        has_inf = gf.FORMATS[name].has_inf if name in gf.FORMATS else None
        out.append((os.path.basename(path), n, has_inf))
    return out


def self_check() -> int:
    """The simulation has to be real. Confirm the RTL runs and answers, and confirm the
    check would notice if the spec side changed -- a comparison against a constant would
    pass forever."""
    if not have_iverilog():
        print("iverilog absent; cannot control a simulation that cannot run")
        return 2
    sys.path.insert(0, os.path.join(ROOT, "conformance"))
    import importlib
    gf = importlib.import_module("gf_ref")

    f = gf.FORMATS["gf8"]
    got = run_rtl(f.width, f.exp_bits, f.mant_bits, f.bias)
    ran = got is not None
    print(f"  gf8 simulation produced a result -> {ran}  {got}")

    want, kind = spec_fp32(gf, "gf8")
    print(f"  spec side for gf8: {want:#010x} ({kind})")
    differs = ran and got[0] != want
    print(f"  and they differ -> {differs}  (this is the finding, not an error here)")

    # The spec side must come from the oracle, not a literal. Perturb the oracle's format
    # and require the expected value to move with it.
    orig = gf.FORMATS["gf8"]
    gf.FORMATS["gf8"] = type(orig)(**{**orig.__dict__, "bias": orig.bias + 1}) \
        if hasattr(orig, "__dict__") else orig
    moved = spec_fp32(gf, "gf8")[0] != want
    gf.FORMATS["gf8"] = orig
    print(f"  expectation follows the oracle, not a literal -> {moved}")

    ok = ran and differs and moved
    print(f"\nself-check: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        raise SystemExit(self_check())
    raise SystemExit(main())
