#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_adder_e24.py — Python bit-model of gf_adder_param at E=24/M=39 (GF64).

Exact transcription of the RTL combinational core (gf_adder_param.v lines 36-204).
Validated against the independent Fraction-based golden oracle (gf_ref.gf_add) on:
  - gf16 (E=6,M=9): 8032/8032 bit-exact
  - gf12 (E=4,M=7): 8032/8032 bit-exact

Purpose: isolate whether gf_adder_param's core logic is correct at E=24/M=39,
or whether the 87/128 silicon discrepancy originates in the compute wrapper
(UART framing, result capture, bitstream provenance).

Generates:
  1. Self-check: Python RTL-model vs Fraction golden oracle
  2. Vector-set file (conformance/verify_adder_e24_vectors.txt) for iverilog testbench

Usage:
  python3 conformance/verify_adder_e24.py [--n N] [--quick]
"""

import sys
import random
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gf_ref import GFFormat, FORMATS, gf_add


def rtl_adder_model(fmt: GFFormat, in_a: int, in_b: int) -> int:
    """
    Exact bit-level transcription of gf_adder_param.v combinational core.
    Returns result_packed (the value registered into out_reg on the next clock).
    """
    E = fmt.exp_bits
    M = fmt.mant_bits
    T = fmt.width  # TOTAL = 1 + E + M
    EXP_MAX = fmt.exp_max
    HAS_INF = 1 if fmt.has_inf else 0

    # Mask inputs
    in_a &= (1 << T) - 1
    in_b &= (1 << T) - 1

    # Field extraction (RTL lines 36-41)
    sa = (in_a >> (T - 1)) & 1
    ea = (in_a >> M) & ((1 << E) - 1)
    ma = in_a & ((1 << M) - 1)
    sb = (in_b >> (T - 1)) & 1
    eb = (in_b >> M) & ((1 << E) - 1)
    mb = in_b & ((1 << M) - 1)

    # Zero detection (RTL lines 44-45)
    a_zero = (ea == 0) and (ma == 0)
    b_zero = (eb == 0) and (mb == 0)

    # Denormal detection (RTL lines 52-53)
    a_denorm = (ea == 0) and (ma != 0)
    b_denorm = (eb == 0) and (mb != 0)

    # NaN detection (RTL lines 58-59) — HAS_INF only
    a_nan = (HAS_INF != 0) and (ea == EXP_MAX) and (ma != 0)
    b_nan = (HAS_INF != 0) and (eb == EXP_MAX) and (mb != 0)

    # Inf detection (RTL lines 66-67) — HAS_INF only
    a_inf = (HAS_INF != 0) and (ea == EXP_MAX) and (ma == 0)
    b_inf = (HAS_INF != 0) and (eb == EXP_MAX) and (mb == 0)

    # NaN input -> canonical quiet NaN (RTL line 127-128)
    if a_nan or b_nan:
        return (0 << (T - 1)) | (EXP_MAX << M) | 1  # {0, all-ones-exp, 0..0, 1}

    # Zero-passthrough (RTL lines 132-137)
    if a_zero and b_zero:
        if sa and sb:
            return (1 << (T - 1))  # -0
        return 0  # +0
    if a_zero:
        return in_b
    if b_zero:
        return in_a

    # Inf handling (RTL lines 140-147)
    if a_inf and b_inf:
        if sa != sb:
            return (0 << (T - 1)) | (EXP_MAX << M) | 1  # qNaN
        return (sa << (T - 1)) | (EXP_MAX << M)  # +/-Inf
    if a_inf:
        return (sa << (T - 1)) | (EXP_MAX << M)
    if b_inf:
        return (sb << (T - 1)) | (EXP_MAX << M)

    # ---- Normal/denormal arithmetic path (RTL lines 69-203) ----

    # Effective exponent: denormals use 1 (RTL lines 70-71)
    ea_eff = 1 if a_denorm else ea
    eb_eff = 1 if b_denorm else eb

    # Mantissa with implicit bit (RTL lines 74-75)
    # MANT_BITS+1 bits wide
    ma_f = ma if a_denorm else ((1 << M) | ma)
    mb_f = mb if b_denorm else ((1 << M) | mb)

    # a_larger (RTL line 77)
    a_larger = (ea_eff > eb_eff) or ((ea_eff == eb_eff) and (ma_f >= mb_f))

    # ediff (RTL lines 78-79) — EXP_BITS+1 bits
    if a_larger:
        ediff = ea_eff - eb_eff
    else:
        ediff = eb_eff - ea_eff

    # Sticky bit (RTL lines 84-89)
    # OR of all bits below G+R from the SHIFTED (smaller) operand
    sticky_bit = 0
    smaller_f = mb_f if a_larger else ma_f
    for j in range(M + 1):
        if j < ediff - 2:
            sticky_bit |= (smaller_f >> j) & 1

    # Extend to MANT_BITS+4 (RTL lines 92-93): {ma_f, 3'b000}
    ma_ext = (ma_f << 3) & ((1 << (M + 4)) - 1)
    mb_ext = (mb_f << 3) & ((1 << (M + 4)) - 1)

    # Align (RTL lines 94-95)
    if a_larger:
        ma_al_raw = ma_ext
        mb_al_raw = (mb_ext >> ediff) if ediff < (M + 4) else 0
    else:
        ma_al_raw = (ma_ext >> ediff) if ediff < (M + 4) else 0
        mb_al_raw = mb_ext

    # Inject sticky into shifted operand bit 0 (RTL lines 97-98)
    if a_larger:
        ma_al = ma_ext
        mb_al = ((mb_al_raw >> 1) << 1) | ((mb_al_raw & 1) | sticky_bit)
    else:
        ma_al = ((ma_al_raw >> 1) << 1) | ((ma_al_raw & 1) | sticky_bit)
        mb_al = mb_ext

    # Result exponent and sign (RTL lines 100-101)
    er = ea_eff if a_larger else eb_eff
    sr = sa if a_larger else sb

    # Effective add/sub (RTL lines 103-108)
    same_sign = (sa == sb)
    # MANT_BITS+5 bits
    sum_add = ma_al + mb_al
    if a_larger:
        sum_sub = ma_al - mb_al
    else:
        sum_sub = mb_al - ma_al
    mant_raw = sum_add if same_sign else sum_sub

    # Normalize (RTL lines 149-187)
    sg = sr
    mw = mant_raw  # MANT_BITS+5 bits
    ew = er  # can grow to EXP_BITS+1 bits

    # Add overflow: same_sign && mw[MANT_BITS+4] (RTL lines 151-156)
    MW_TOP = M + 4
    if same_sign and ((mw >> MW_TOP) & 1):
        old_sticky = mw & 1
        mw = mw >> 1
        mw = (mw & ~1) | ((mw & 1) | old_sticky)
        ew = ew + 1

    # Subtraction normalize (RTL lines 159-164)
    MW_TOP_M1 = M + 3
    if (not same_sign) and mw != 0:
        for _ in range(M + 3):
            if not ((mw >> MW_TOP_M1) & 1) and ew != 0:
                mw = (mw << 1) & ((1 << (M + 5)) - 1)
                ew = ew - 1
            else:
                break

    # Subtraction subnormal result: ew==0 (RTL lines 169-173)
    if (not same_sign) and mw != 0 and ew == 0:
        old_sticky = mw & 1
        mw = mw >> 1
        mw = (mw & ~1) | ((mw & 1) | old_sticky)

    # Round-half-to-even using GRS (RTL lines 175-178)
    # G=bit2, R=bit1, S=bit0
    g = (mw >> 2) & 1
    r = (mw >> 1) & 1
    s = mw & 1
    upper = mw >> 3  # mantissa portion MANT_BITS+2 bits

    if g and (r or s or ((mw >> 3) & 1)):
        mant_rounded = upper + 1
    else:
        mant_rounded = upper

    # Overflow on rounding (RTL lines 179-182)
    if (mant_rounded >> (M + 1)) & 1:
        mant_rounded = mant_rounded >> 1
        ew = ew + 1

    # Denormal result detection (addition only) (RTL lines 186-187)
    if same_sign and not ((mw >> MW_TOP_M1) & 1) and ew <= 1:
        ew = 0

    # Pack (RTL lines 189-203)
    MASK_T = (1 << T) - 1
    if mw == 0:
        result_packed = 0
    elif HAS_INF and (((ew >> E) & 1) or ((ew & EXP_MAX) == EXP_MAX)):
        result_packed = (sg << (T - 1)) | (EXP_MAX << M)  # +/-Inf
    elif (not HAS_INF) and ((ew >> E) & 1):
        result_packed = (sg << (T - 1)) | (EXP_MAX << M) | ((1 << M) - 1)  # max-finite
    elif ew == 0:
        result_packed = (sg << (T - 1)) | (0 << M) | (mant_rounded & ((1 << M) - 1))
    else:
        result_packed = (sg << (T - 1)) | ((ew & ((1 << E) - 1)) << M) | (mant_rounded & ((1 << M) - 1))

    return result_packed & MASK_T


def gen_vectors(fmt: GFFormat, n: int = 1000, quick: bool = False):
    """Generate a diverse vector set covering edge cases + random."""
    T = fmt.width
    M = fmt.mant_bits
    E = fmt.exp_bits
    BIAS = fmt.bias

    vectors = []
    seen = set()

    def add(a, b):
        a &= (1 << T) - 1
        b &= (1 << T) - 1
        key = (a, b)
        if key not in seen:
            seen.add(key)
            vectors.append((a, b))

    if quick:
        n = 200

    # ---- Edge cases ----
    # Zeros
    add(0, 0)
    add(0, 1 << (T - 1))  # +0, -0
    add(1 << (T - 1), 0)

    # 1.0 and -1.0
    one_pos = BIAS << M
    one_neg = (1 << (T - 1)) | one_pos
    add(one_pos, one_pos)    # 1+1=2
    add(one_neg, one_pos)    # -1+1=0
    add(one_pos, one_neg)    # 1+(-1)=0
    add(one_neg, one_neg)    # -1+(-1)=-2
    add(one_pos, 0)          # identity
    add(0, one_pos)          # identity
    add(one_neg, 0)          # identity
    add(0, one_neg)          # identity

    # Powers of 2
    for i in range(-3, 4):
        exp = BIAS + i
        if 1 <= exp < ((1 << E) - 1):
            val = exp << M
            add(val, val)
            add(val | (1 << (T - 1)), val)  # negate a
            add(val, one_pos)

    # Denormals
    add(1, 0)               # smallest denormal + 0
    add(1, 1)               # two denormals
    add(1, one_pos)         # denormal + 1.0
    add(1 | (1 << (T - 1)), one_pos)  # -denormal + 1.0

    # Inf/NaN (if HAS_INF)
    if fmt.has_inf:
        exp_max = (1 << E) - 1
        pos_inf = exp_max << M
        neg_inf = (1 << (T - 1)) | pos_inf
        qnan = (exp_max << M) | 1
        add(pos_inf, one_pos)    # Inf + finite
        add(neg_inf, one_pos)    # -Inf + finite
        add(pos_inf, neg_inf)    # Inf + (-Inf) = NaN
        add(pos_inf, pos_inf)    # Inf + Inf
        add(qnan, one_pos)       # NaN + finite
        add(qnan, 0)             # NaN + 0
        add(one_pos, qnan)       # finite + NaN

    # Near-overflow / max-finite
    if fmt.has_inf:
        max_e = (1 << E) - 2  # exp_max - 1
    else:
        max_e = (1 << E) - 1  # exp_max
    max_fin = (max_e << M) | ((1 << M) - 1)
    add(max_fin, max_fin)
    add(max_fin, one_pos)
    add(max_fin | (1 << (T - 1)), max_fin)  # cancellation

    # Near-denormal boundary
    add(one_pos, 1)         # 1.0 + smallest denormal
    add(one_pos - 1, 0)     # just below 1.0 (exp=BIAS, mant=max)
    add((1 << M), 0)        # smallest normal (exp=1)

    # Cancellation (close values, different signs)
    for delta in [1, 2, 3, (1 << (M // 2)), (1 << M) - 1]:
        add(one_pos | (1 << (T - 1)), one_pos - delta)  # -1.0 + (1.0 - delta)

    # ---- Random ----
    if not quick:
        # Normal-range randoms
        for _ in range(n):
            exp_a = random.randint(max(1, BIAS - 10), min(max_e, BIAS + 10))
            exp_b = random.randint(max(1, BIAS - 10), min(max_e, BIAS + 10))
            mant_a = random.randint(0, (1 << M) - 1) if M <= 20 else random.randint(0, (1 << 20) - 1) * ((1 << M) // (1 << 20))
            mant_b = random.randint(0, (1 << M) - 1) if M <= 20 else random.randint(0, (1 << 20) - 1) * ((1 << M) // (1 << 20))
            sign_a = random.randint(0, 1)
            sign_b = random.randint(0, 1)
            a = (sign_a << (T - 1)) | (exp_a << M) | (mant_a & ((1 << M) - 1))
            b = (sign_b << (T - 1)) | (exp_b << M) | (mant_b & ((1 << M) - 1))
            add(a, b)

        # Fully random (covers specials, denormals, etc.)
        for _ in range(n // 2):
            a = random.randint(0, (1 << T) - 1) if T <= 32 else random.randint(0, (1 << 32) - 1)
            b = random.randint(0, (1 << T) - 1) if T <= 32 else random.randint(0, (1 << 32) - 1)
            add(a, b)

    return vectors


def main():
    parser = argparse.ArgumentParser(description="Verify gf_adder_param at E=24/M=39")
    parser.add_argument("--n", type=int, default=1000, help="Number of random vectors per category")
    parser.add_argument("--quick", action="store_true", help="Quick mode (200 vectors)")
    parser.add_argument("--format", default="gf64", help="GF format to verify (default: gf64)")
    parser.add_argument("--validate", action="store_true", help="First validate on gf16+gf12")
    parser.add_argument("--write-vectors", action="store_true", help="Write iverilog vector file")
    args = parser.parse_args()

    random.seed(42)  # reproducible

    # ---- Step 1: Validate the RTL model on known-good formats ----
    if args.validate or not args.quick:
        print("=== Validating RTL model on known-good formats ===")
        for fname in ["gf16", "gf12"]:
            fmt = FORMATS[fname]
            vectors = gen_vectors(fmt, n=500, quick=True)
            ok = 0
            fail = 0
            for a, b in vectors:
                rtl = rtl_adder_model(fmt, a, b)
                gold = gf_add(fmt, a, b)
                if rtl == gold:
                    ok += 1
                else:
                    fail += 1
                    if fail <= 3:
                        print(f"  {fname} MISMATCH: a=0x{a:0{fmt.width//4+1}x} b=0x{b:0{fmt.width//4+1}x} "
                              f"rtl=0x{rtl:0{fmt.width//4+1}x} gold=0x{gold:0{fmt.width//4+1}x}")
            print(f"  {fname}: {ok}/{ok+fail} bit-exact (fails={fail})")

    # ---- Step 2: Verify target format ----
    fmt = FORMATS[args.format]
    print(f"\n=== Verifying gf_adder_param at {args.format} (E={fmt.exp_bits}, M={fmt.mant_bits}) ===")

    vectors = gen_vectors(fmt, n=args.n, quick=args.quick)
    print(f"Total vectors: {len(vectors)}")

    ok = 0
    fail = 0
    fails_detail = []

    for a, b in vectors:
        rtl = rtl_adder_model(fmt, a, b)
        gold = gf_add(fmt, a, b)
        if rtl == gold:
            ok += 1
        else:
            fail += 1
            if len(fails_detail) < 10:
                fails_detail.append((a, b, rtl, gold))

    print(f"Result: {ok}/{ok+fail} bit-exact (fails={fail})")

    if fails_detail:
        hw = fmt.width // 4 + 1
        print(f"\nFirst {len(fails_detail)} mismatches:")
        for a, b, rtl, gold in fails_detail:
            print(f"  a=0x{a:0{hw}x} b=0x{b:0{hw}x} rtl=0x{rtl:0{hw}x} gold=0x{gold:0{hw}x}")

    # ---- Step 3: Write vector file for iverilog testbench ----
    if args.write_vectors:
        vpath = Path(__file__).parent / f"verify_adder_{args.format}_vectors.txt"
        with open(vpath, "w") as f:
            f.write(f"# verify_adder_{args.format}_vectors.txt — auto-generated by verify_adder_e24.py\n")
            f.write(f"# Format: {args.format} E={fmt.exp_bits} M={fmt.mant_bits} W={fmt.width}\n")
            f.write(f"# Each line: a_hex b_hex expected_hex\n")
            for a, b in vectors:
                gold = gf_add(fmt, a, b)
                hw = fmt.width // 4
                f.write(f"{a:0{hw}x} {b:0{hw}x} {gold:0{hw}x}\n")
        print(f"\nVector file: {vpath} ({len(vectors)} vectors)")

    # ---- Step 4: Write iverilog testbench ----
    if args.write_vectors:
        tbpath = Path(__file__).parent / f"tb_gf_adder_{args.format}.v"
        T = fmt.width
        tb = f"""`timescale 1ns / 1ps
// Auto-generated testbench for gf_adder_param at {args.format} (E={fmt.exp_bits}, M={fmt.mant_bits})
module tb_gf_adder_{args.format};
    reg clk = 0;
    reg rst = 1;
    reg in_valid = 0;
    reg [{T-1}:0] in_a, in_b;
    wire in_ready;
    wire out_valid;
    wire [{T-1}:0] out_y;
    reg out_ready = 1;

    gf_adder_param #(
        .EXP_BITS({fmt.exp_bits}),
        .MANT_BITS({fmt.mant_bits}),
        .HAS_INF({1 if fmt.has_inf else 0})
    ) DUT (
        .clk(clk), .rst(rst),
        .in_valid(in_valid), .in_a(in_a), .in_b(in_b), .in_ready(in_ready),
        .out_valid(out_valid), .out_y(out_y), .out_ready(out_ready)
    );

    always #5 clk = ~clk;

    integer fd, errors = 0, total = 0;
    reg [{T-1}:0] a, b, expected;
    reg [255:0] line;
    integer r;

    initial begin
        fd = $fopen("conformance/verify_adder_{args.format}_vectors.txt", "r");
        if (fd == 0) begin
            $display("ERROR: Cannot open vector file");
            $finish;
        end

        #20 rst = 0;
        #10;

        // Skip header lines (starting with #)
        r = $fgets(line, fd);
        r = $fgets(line, fd);
        r = $fgets(line, fd);

        while (!$feof(fd)) begin
            r = $fscanf(fd, "%h %h %h\\n", a, b, expected);
            if (r != 3) continue;

            @(posedge clk);
            in_valid = 1; in_a = a; in_b = b;
            @(posedge clk);
            in_valid = 0;

            // Wait for output
            wait(out_valid);
            @(posedge clk);

            total = total + 1;
            if (out_y !== expected) begin
                errors = errors + 1;
                if (errors <= 10)
                    $display("MISMATCH: a=%h b=%h got=%h exp=%h", a, b, out_y, expected);
            end
        end

        $display("RESULT: {args.format} %0d/%0d bit-exact (errors=%0d)", total - errors, total, errors);
        $fclose(fd);
        if (errors == 0)
            $display("ALL_PASS");
        else
            $display("FAIL");
        $finish;
    end
endmodule
"""
        with open(tbpath, "w") as f:
            f.write(tb)
        print(f"Testbench: {tbpath}")

    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
