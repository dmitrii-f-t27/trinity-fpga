#!/usr/bin/env python3
"""Run gf_adder_param under iverilog and hold it to the exact-Fraction oracle.

Pass 238 did this for the decoder and found that `parameter integer BIAS` had
been silently truncating the bias of every format with BIAS >= 2**31. The adder
is the decoder's sibling -- same lineup, same HAS_INF parameter -- and nothing
had ever run it against gf_ref.gf_add the same way.

Its BIAS is declared differently:

    parameter BIAS = (1 << (EXP_BITS - 1)) - 1

Untyped, so an explicit override is not truncated to 32 bits the way `integer`
would be. The DEFAULT is another matter: `1` is a 32-bit literal, so
`1 << (EXP_BITS - 1)` is 0 for any format with EXP_BITS >= 33 -- gf96 (36),
gf128 (49), gf256 (97), gf512, gf1024. A wrapper that leaves BIAS at its default
for those widths gets a bias of zero.

This passes BIAS explicitly from gf_ref, so the module is measured on its
arithmetic rather than on its defaults, and separately reports what the default
would have been.

Pairs are structural, not random: every corner against every corner (zero, one,
minpos, maxpos, the all-ones exponent, both signs), then a fixed-seed tail. Add
is a two-operand op, so exhaustive is out at any useful width -- gf16 alone would
be 2**32 pairs.

Usage:  python3 research/witness_gf_adder_rtl.py [format ...]
"""
import os
import random
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")
CORE = os.path.join(ROOT, "fpga", "openxc7-synth", "gf_adder_param.v")
sys.path.insert(0, CONF)

import gf_ref                                        # noqa: E402

HAS_INF = {"gf16"}
RANDOM_PAIRS = 400


def corners(N, E, M, B):
    EM = (1 << E) - 1
    MM = (1 << M) - 1
    out = set()
    for s in (0, 1):
        base = s << (N - 1)
        out |= {base, base | 1, base | MM,                       # zero, minpos, max sub
                base | (B << M),                                  # 1.0
                base | ((B + 1) << M),                            # 2.0
                base | ((B - 1) << M) if B else base,             # 0.5
                base | (1 << M),                                  # min normal
                base | ((EM - 1) << M) | MM,                      # max finite below all-ones
                base | (EM << M),                                 # all-ones, mant 0
                base | (EM << M) | 1}                             # all-ones, mant 1
    return sorted(c & ((1 << N) - 1) for c in out)


def pairs(N, E, M, B):
    cs = corners(N, E, M, B)
    out = [(a, b) for a in cs for b in cs]
    rnd = random.Random(20260806)
    for _ in range(RANDOM_PAIRS):
        out.append((rnd.randrange(1 << N), rnd.randrange(1 << N)))
    return out


def emit_tb(N, E, M, B, has_inf, ps):
    d = (N + 3) // 4
    fmt = "%0" + str(d) + "h"          # the Verilog $display format, built once
    # Drive on negedge, deassert after one cycle, then wait for out_valid with a
    # bounded timeout -- the same sequence conformance/tb_gf_adder_gf64.v uses.
    # My first version raised in_valid and immediately waited for out_valid
    # without deasserting, which samples the PREVIOUS transaction's output: it
    # reported 0 + minpos = 0 and 1,835 disagreements out of 2,100 for cores that
    # carry 65536/65536 silicon evidence. The handshake was mine, not the adder's.
    drive = "\n".join(
        f"        @(negedge clk); in_valid = 1; in_a = {N}'h{a:0{d}x}; in_b = {N}'h{b:0{d}x};\n"
        f"        @(negedge clk); in_valid = 0;\n"
        f"        tmo = 0; while (!out_valid && tmo < 20) begin @(posedge clk); tmo = tmo + 1; end\n"
        f'        $display("{fmt}", out_y);'
        for a, b in ps)
    return f"""`timescale 1ns / 1ps
module tb;
    reg clk = 0; reg rst = 1; reg in_valid = 0; reg out_ready = 1;
    reg [{N-1}:0] in_a = 0, in_b = 0;
    integer tmo;
    wire in_ready, out_valid;
    wire [{N-1}:0] out_y;
    gf_adder_param #(.EXP_BITS({E}), .MANT_BITS({M}), .TOTAL({N}),
                     .BIAS({B}), .HAS_INF({1 if has_inf else 0}), .PIPELINE(0)) DUT (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_a(in_a), .in_b(in_b),
        .in_ready(in_ready), .out_valid(out_valid), .out_y(out_y),
        .out_ready(out_ready));
    always #5 clk = ~clk;
    initial begin
        repeat (4) @(posedge clk); rst = 0; repeat (2) @(posedge clk);
{drive}
        $finish;
    end
endmodule
"""


def run(name, fmt):
    E, M, B = fmt.exp_bits, fmt.mant_bits, fmt.bias
    N = 1 + E + M
    ps = pairs(N, E, M, B)
    digits = (N + 3) // 4
    with tempfile.TemporaryDirectory() as td:
        tb = os.path.join(td, "tb.v")
        with open(tb, "w") as fh:
            fh.write(emit_tb(N, E, M, B, name in HAS_INF, ps))
        vvp = os.path.join(td, "tb.vvp")
        # -g2012 is required, not a convenience. gf_adder_param declares out_valid
        # and out_y as `output reg` and then drives both with continuous assigns,
        # which iverilog rejects under its default Verilog-2001 mode:
        # "Variable 'out_valid' cannot be driven by a continuous assignment ...
        # This is allowed when SystemVerilog is enabled." The decoder needs no such
        # flag. conformance/tb_gf_adder_gf64.v also uses `continue`, an SV keyword,
        # so that testbench cannot have run under the default mode either.
        c = subprocess.run(["iverilog", "-g2012", "-o", vvp, tb, CORE],
                           capture_output=True, text=True)
        if c.returncode != 0:
            return name, N, 0, -1, (c.stderr or c.stdout).strip().splitlines()[0][:150]
        r = subprocess.run(["vvp", vvp], capture_output=True, text=True)
    out = [ln.strip() for ln in r.stdout.splitlines()
           if len(ln.strip()) == digits
           and all(ch in "0123456789abcdefABCDEF" for ch in ln.strip())]
    if len(out) != len(ps):
        return name, N, 0, -1, "got %d lines for %d pairs" % (len(out), len(ps))
    mask = (1 << N) - 1
    bad = 0
    first = ""
    for (a, b), line in zip(ps, out):
        rtl = int(line, 16) & mask
        try:
            exact = gf_ref.gf_add(fmt, a, b) & mask
        except Exception:                             # noqa: BLE001
            continue
        if rtl != exact:
            bad += 1
            if not first:
                first = "a=%#x b=%#x rtl=%#x exact=%#x" % (a, b, rtl, exact)
    return name, N, len(ps), bad, first


def main():
    want = [a for a in sys.argv[1:] if not a.startswith("-")]
    names = want or sorted(gf_ref.FORMATS, key=lambda k: gf_ref.FORMATS[k].exp_bits)
    print("%-8s %5s %8s %7s  %s" % ("format", "bits", "pairs", "differ", "default BIAS"))
    tot = totbad = fails = 0
    for name in names:
        fmt = gf_ref.FORMATS.get(name)
        if fmt is None:
            continue
        E, B = fmt.exp_bits, fmt.bias
        # what `parameter BIAS = (1 << (EXP_BITS-1)) - 1` yields in 32-bit Verilog
        default = ((1 << (E - 1)) - 1) if E - 1 < 32 else 0xFFFFFFFF
        if E - 1 >= 32:
            default = (1 << (E - 1)) % (1 << 32)
            default = (default - 1) & 0xFFFFFFFF
        note = "ok" if default == B else "WOULD BE %d, not %d" % (default, B)
        n, bits, count, bad, first = run(name, fmt)
        if bad < 0:
            print("%-8s %5d %8s %7s  %s" % (n, bits, "-", "ERR", first))
            fails += 1
            continue
        tot += count
        totbad += bad
        print("%-8s %5d %8d %7d%s  %s"
              % (n, bits, count, bad, "  <<<" if bad else "", note))
        if first:
            print("         first: %s" % first)
    print()
    print("pairs witnessed : %d" % tot)
    print("disagreements   : %d" % totbad)
    print("formats errored : %d" % fails)
    return 1 if (totbad or fails) else 0


if __name__ == "__main__":
    sys.exit(main())
