#!/usr/bin/env python3
"""What would round-to-nearest cost, and what would it buy?

Pass 241 fixed the exponent wrap in the operand narrowing and deliberately left
the mantissa alone, calling truncation "a separate decision about cost, while
wrapping is simply a wrong answer". That was the right split, and it left the
decision without numbers. This produces them.

The narrowing keeps the top 23 bits of a wider significand and discards the rest:

    wire [22:0] mant32 = mant[111:89];        // binary128: 89 bits dropped

Round-to-nearest-even needs the guard bit, a sticky OR of everything below it, and
an increment that can carry into the exponent:

    guard    = mant[88]
    sticky   = |mant[87:0]
    round_up = guard & (sticky | mant32[0])
    {carry, mant_rne} = mant32 + round_up

Two questions, both answered here rather than argued:

  CORRECTNESS  over a structural operand set, how many results does truncation
               get wrong that rounding gets right -- measured against the exact
               value rounded once, which is conformance/gf_decode_golden.
  COST         what rounding adds in LUTs, from yosys on the two narrowings
               synthesised side by side.

Usage:  python3 research/witness_rounding.py
"""
import os
import re
import subprocess
import sys
import tempfile
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")
sys.path.insert(0, CONF)

FP32_INF = 0x7F800000
LUTS = re.compile(r"^\s+(\d+)\s+LUT[1-6]\s*$", re.M)

# (name, E, M, BIAS) -- the widths whose wrappers narrow into fp32
CASES = [
    ("binary128", 15, 112, 16383),
    ("binary256", 19, 236, 262143),
    ("cray_float", 15, 48, 16384),
    ("x87_fp80", 15, 63, 16383),
]


def exact_fp32(sign, exp, mant, E, M, BIAS):
    """The exact value rounded once to fp32, ties to even."""
    if exp == 0 and mant == 0:
        return sign << 31
    if exp == (1 << E) - 1:
        return (sign << 31) | (0x7FC00001 if mant else FP32_INF)
    v = Fraction((1 << M) + mant, 1 << M) * Fraction(2) ** (exp - BIAS)
    e = exp - BIAS
    if e > 127:
        return (sign << 31) | FP32_INF
    if e < -149:
        return sign << 31
    if e < -126:
        scaled = v * Fraction(2) ** 149
        exp_field = 0
    else:
        scaled = v / Fraction(2) ** e * (1 << 23)
        exp_field = e + 127
    q, r = divmod(scaled.numerator, scaled.denominator)
    if r * 2 > scaled.denominator or (r * 2 == scaled.denominator and q & 1):
        q += 1
    if exp_field == 0:
        return (sign << 31) | q
    frac = q - (1 << 23)
    if frac >= (1 << 23):
        frac = 0
        exp_field += 1
        if exp_field >= 0xFF:
            return (sign << 31) | FP32_INF
    return (sign << 31) | (exp_field << 23) | frac


def narrowed(sign, exp, mant, E, M, BIAS, round_it):
    """The wrapper's narrowing, with truncation or with RNE."""
    if exp == 0 and mant == 0:
        return sign << 31
    if exp == (1 << E) - 1:
        return (sign << 31) | (0x7FC00001 if mant else FP32_INF)
    v = exp - BIAS + 127
    if v > 254:
        return (sign << 31) | FP32_INF
    if v < 1:
        return sign << 31
    top = mant >> (M - 23)
    if round_it:
        guard = (mant >> (M - 24)) & 1
        sticky = 1 if (mant & ((1 << (M - 24)) - 1)) else 0
        if guard and (sticky or (top & 1)):
            top += 1
            if top >> 23:
                top = 0
                v += 1
                if v > 254:
                    return (sign << 31) | FP32_INF
    return (sign << 31) | (v << 23) | (top & 0x7FFFFF)


def cases_for(E, M, BIAS):
    out = []
    MM = (1 << M) - 1
    for sign in (0, 1):
        for exp in (1, BIAS - 126, BIAS - 1, BIAS, BIAS + 1, BIAS + 127, (1 << E) - 2):
            if not 0 <= exp < (1 << E):
                continue
            for mant in (0, 1, MM, MM // 2, MM // 3, (1 << (M - 24)),
                         (1 << (M - 24)) - 1, (1 << (M - 23)) | (1 << (M - 24))):
                out.append((sign, exp, mant & MM))
    return out


def lut_cost():
    """Synthesise the two narrowings side by side and diff the LUT counts."""
    def build(round_it):
        rnd = """
    wire        g  = mant[88];
    wire        st = |mant[87:0];
    wire        up = g & (st | top[0]);
    wire [23:0] sum = top + up;
    wire [22:0] mant32 = sum[23] ? 23'b0 : sum[22:0];
    wire [7:0]  exp32  = sum[23] ? (exp32_s[7:0] + 8'd1) : exp32_s[7:0];
""" if round_it else """
    wire [22:0] mant32 = top;
    wire [7:0]  exp32  = exp32_s[7:0];
"""
        return """`timescale 1ns/1ps
module narrow(input sign, input [14:0] exp, input [111:0] mant, output [31:0] y);
    wire signed [15:0] exp32_s = $signed({1'b0, exp}) - 16'sd16383 + 16'sd127;
    wire [22:0] top = mant[111:89];
%s
    assign y = {sign, exp32, mant32};
endmodule
""" % rnd

    counts = []
    for round_it in (False, True):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "n.v")
            with open(p, "w") as fh:
                fh.write(build(round_it))
            r = subprocess.run(
                ["yosys", "-p", "read_verilog %s; hierarchy -top narrow; "
                                "synth_xilinx -flatten -nodsp; stat" % p],
                capture_output=True, text=True)
            got = LUTS.findall(r.stdout + r.stderr)
            half = len(got) // 2 or len(got)
            # No LUT lines is not a failure -- a pure slice is wiring, and wiring
            # costs zero logic. That is the whole point of the comparison.
            ok = "ERROR" not in (r.stdout + r.stderr)
            counts.append((sum(int(x) for x in got[-half:]) if got else 0) if ok else None)
    return counts


def main():
    print("CORRECTNESS -- results the narrowing gets wrong, against the exact value")
    print("%-12s %6s %10s %10s" % ("format", "cases", "truncating", "rounding"))
    tot_t = tot_r = tot_n = 0
    for name, E, M, BIAS in CASES:
        cs = cases_for(E, M, BIAS)
        t = r = 0
        for sign, exp, mant in cs:
            want = exact_fp32(sign, exp, mant, E, M, BIAS)
            if narrowed(sign, exp, mant, E, M, BIAS, False) != want:
                t += 1
            if narrowed(sign, exp, mant, E, M, BIAS, True) != want:
                r += 1
        print("%-12s %6d %10d %10d" % (name, len(cs), t, r))
        tot_t += t
        tot_r += r
        tot_n += len(cs)
    print("%-12s %6d %10d %10d" % ("total", tot_n, tot_t, tot_r))
    print()
    trunc, rnd = lut_cost()
    print("COST -- the binary128 narrowing synthesised both ways")
    print("  truncating : %s LUTs" % trunc)
    print("  rounding   : %s LUTs" % rnd)
    if trunc is not None and rnd is not None:
        if trunc:
            print("  difference : %+d LUTs (%.1f%%)" % (rnd - trunc, 100.0 * (rnd - trunc) / trunc))
        else:
            print("  difference : %+d LUTs -- truncation is a pure slice, so it is"
                  " wiring and costs no logic at all" % (rnd - trunc))
    print()
    print("This measures the decision pass 241 deferred. It does not take it:")
    print("changing the mantissa path moves every result, not just the wrong ones.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
