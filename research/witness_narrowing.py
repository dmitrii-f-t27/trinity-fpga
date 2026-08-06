#!/usr/bin/env python3
"""Does the operand narrowing saturate, and did it wrap before?

The compute wrappers cannot be elaborated on their own -- they instantiate
STARTUPE2, a Xilinx primitive -- so this lifts the narrowing expressions out of
one of them verbatim and runs both versions side by side under iverilog:

    OLD:  fp32 = {sign, exp32_s[7:0], mant[111:89]}
    NEW:  exp32_s > 254 -> {sign, 8'hFF, 0}      (+/-Inf)
          exp32_s < 1   -> {sign, 8'd0,  0}      (+/-0)
          otherwise     -> {sign, exp32_s[7:0], mant[111:89]}

and holds both to the answer the format asks for: an exponent outside fp32's
window saturates. It does not touch the mantissa question -- the low 89 bits are
still truncated rather than rounded in both versions, because that is a separate
decision about cost, while wrapping is simply a wrong answer.

Usage:  python3 research/witness_narrowing.py
"""
import os
import subprocess
import sys
import tempfile

E, M, BIAS = 15, 112, 16383       # binary128
FP32_INF = 0x7F800000


def expected(sign, exp, mant):
    """What the narrowing must produce, mantissa truncation included."""
    if exp == 0 and mant == 0:
        return sign << 31
    if exp == (1 << E) - 1:
        return (sign << 31) | (0x7FC00000 if mant else FP32_INF)
    v = exp - BIAS + 127
    if v > 254:
        return (sign << 31) | FP32_INF
    if v < 1:
        return sign << 31
    return (sign << 31) | (v << 23) | (mant >> (M - 23))


def same(got, want):
    """Equal as an fp32 answer. IEEE 754 does not mandate a NaN sign or payload,
    so NaN is compared by class; everything else, including the sign of zero, is
    compared exactly."""
    if got == want:
        return True
    gn = ((got >> 23) & 0xFF) == 0xFF and (got & 0x7FFFFF)
    wn = ((want >> 23) & 0xFF) == 0xFF and (want & 0x7FFFFF)
    return bool(gn and wn)


def cases():
    out = []
    for sign in (0, 1):
        for exp in (0, 1, 2, BIAS - 200, BIAS - 127, BIAS - 126, BIAS,
                    BIAS + 1, BIAS + 127, BIAS + 128, BIAS + 200,
                    (1 << E) - 2, (1 << E) - 1):
            for mant in (0, 1, (1 << M) - 1, 1 << (M - 1)):
                out.append((sign, exp, mant))
    return out


def emit(cs):
    body = "\n".join(
        f"        sign = 1'b{s}; exp = {E}'d{e}; mant = {M}'d{m}; #1"
        f' $display("%08h %08h", old_fp32, new_fp32);'
        for s, e, m in cs)
    return f"""`timescale 1ns / 1ps
module tb;
    reg sign; reg [{E-1}:0] exp; reg [{M-1}:0] mant;
    wire zero = (exp == {E}'d0) && (mant == {M}'d0);
    wire nan  = (exp == {E}'h{(1 << E) - 1:X}) && (|mant);
    wire inf  = (exp == {E}'h{(1 << E) - 1:X}) && (mant == {M}'d0);
    wire signed [15:0] exp32_s = $signed({{1'b0, exp}}) - 16'sd{BIAS} + 16'sd127;
    wire [7:0]  exp32  = exp32_s[7:0];
    wire [22:0] mant32 = mant[{M-1}:{M-23}];
    reg [31:0] old_fp32, new_fp32;
    always @(*) begin
        if (zero) old_fp32 = 32'h00000000;
        else if (nan) old_fp32 = 32'h7FC00000;
        else if (inf) old_fp32 = {{sign, 8'hFF, 23'b0}};
        else old_fp32 = {{sign, exp32, mant32}};
    end
    always @(*) begin
        if (zero) new_fp32 = {{sign, 31'b0}};
        else if (nan) new_fp32 = 32'h7FC00000;
        else if (inf) new_fp32 = {{sign, 8'hFF, 23'b0}};
        else if (exp32_s > 16'sd254) new_fp32 = {{sign, 8'hFF, 23'b0}};
        else if (exp32_s < 16'sd1) new_fp32 = {{sign, 8'd0, 23'b0}};
        else new_fp32 = {{sign, exp32, mant32}};
    end
    initial begin
{body}
        $finish;
    end
endmodule
"""


def main():
    cs = cases()
    with tempfile.TemporaryDirectory() as td:
        tb = os.path.join(td, "tb.v")
        with open(tb, "w") as fh:
            fh.write(emit(cs))
        vvp = os.path.join(td, "tb.vvp")
        c = subprocess.run(["iverilog", "-o", vvp, tb], capture_output=True, text=True)
        if c.returncode != 0:
            print((c.stderr or c.stdout).strip()[:400])
            return 2
        r = subprocess.run(["vvp", vvp], capture_output=True, text=True)
    rows = [ln.split() for ln in r.stdout.splitlines() if len(ln.split()) == 2
            and all(len(t) == 8 for t in ln.split())]
    if len(rows) != len(cs):
        print("got %d result lines for %d cases" % (len(rows), len(cs)))
        return 2
    old_bad = new_bad = 0
    shown = 0
    for (s, e, m), (o, n) in zip(cs, rows):
        want = expected(s, e, m)
        o, n = int(o, 16), int(n, 16)
        if not same(o, want):
            old_bad += 1
            if shown < 4:
                print("  wrapped: sign=%d exp=%d -> old %#010x, want %#010x"
                      % (s, e, o, want))
                shown += 1
        if not same(n, want):
            new_bad += 1
            print("  STILL WRONG: sign=%d exp=%d mant=%#x -> new %#010x, want %#010x"
                  % (s, e, m, n, want))
    print()
    print("cases                       : %d" % len(cs))
    print("wrong BEFORE the change     : %d" % old_bad)
    print("wrong AFTER the change      : %d" % new_bad)
    return 1 if new_bad else 0


if __name__ == "__main__":
    sys.exit(main())
