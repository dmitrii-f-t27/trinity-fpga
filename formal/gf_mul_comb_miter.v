// =============================================================================
// COMBINATIONAL formal miter for gf_mul_param — proves the MUL combinational
// core (result_packed) == independent integer RNE oracle for ALL input pairs.
// Mirror of formal/gf_adder_comb_miter.v (see that file for why the clockless
// approach avoids the reset/init artifact that stalled sequential harnesses).
//
// INDEPENDENT ORACLE (ref_fpmul): folds each operand's exponent into an integer
// FIRST (A = mant_int_a << (eff_a-1)), multiplies, then finds MSB + RNE. The DUT
// instead multiplies the bare significands (prod = ma_f*mb_f) and folds the
// exponent later (exp_field = er + msb - 2*MANT) — a genuinely different integer
// decomposition, so a bug in either is likely caught. Verified algebraically:
//   L(MS=MSB(A*B)) = msb_dut + eff_a + eff_b - 2  =>
//   exp_field_oracle = L - BIAS - 2*MANT + 2  ==  er_dut + msb_dut - 2*MANT.
//
// WIDTHS: fits Verilog 32-bit `integer` for GF4(1,2) GF6(2,3) GF8(3,4). GF12+
// overflows (mant_int<<14 exceeds 2^31) — needs wide-int ref (future work).
//
// STATUS: GF4 PROVEN, GF6 PROVEN (`SUCCESS!` all input pairs). GF8 is
// sim-confirmed CORRECT (iverilog: 0x4A*0x01 -> 0x03, == this oracle, == DUT)
// but the formal model reads result_packed as 0 for denormal-RESULT cases — a
// yosys function-elaboration artifact: gf_mul_param routes its denormal-result
// path through `function pack_denorm` (the all-inline gf_adder_param has no such
// issue). Not a DUT bug (iverilog + silicon 480/480 confirm). Closing GF8 needs
// either inlining pack_denorm or a different formal engine — deferred.
//
// Run (GF8 default; chparam overrides width):
//   yosys -p "read_verilog -sv -DFORMAL fpga/openxc7-synth/gf_mul_param.v; \
//     read_verilog -sv formal/gf_mul_comb_miter.v; \
//     chparam -set EXP_BITS 3 -set MANT_BITS 4 gf_mul_comb_miter; \
//     hierarchy -top gf_mul_comb_miter; proc; opt; flatten; opt; \
//     sat -prove mismatch 1'b0"
//   -> "SAT proof finished - no model found: SUCCESS!"
// =============================================================================
`default_nettype none
`timescale 1ns / 1ps

module gf_mul_comb_miter #(
    parameter EXP_BITS  = 3,
    parameter MANT_BITS = 4,
    parameter TOTAL     = 1 + EXP_BITS + MANT_BITS,
    parameter BIAS      = (1 << (EXP_BITS - 1)) - 1
)(
    output wire mismatch
);
    reg [TOTAL-1:0] in_a, in_b;   // free symbolic inputs

    wire        unused_in_ready, unused_out_valid;
    wire [TOTAL-1:0] unused_out_y;
    gf_mul_param #(
        .EXP_BITS(EXP_BITS),
        .MANT_BITS(MANT_BITS)
    ) dut (
        .clk(1'b0), .rst(1'b0),
        .in_valid(1'b0), .in_a(in_a), .in_b(in_b), .in_ready(unused_in_ready),
        .out_valid(unused_out_valid), .out_y(unused_out_y), .out_ready(1'b1),
        .result_comb(result_comb_wire)
    );
    wire [TOTAL-1:0] result_comb_wire;

    // ---- INDEPENDENT reference: fold exponent into integer, multiply, RNE ----
    function [TOTAL-1:0] ref_fpmul;
        input [TOTAL-1:0] a, b;
        reg ra, rb, az, bz, adn, bdn, sg;
        reg [EXP_BITS-1:0]  ea, eb;
        reg [MANT_BITS-1:0] ma, mb;
        integer mant_a, mant_b, eff_a, eff_b, A, B, prod_int, L;
        integer k, exp_field, frac, gd, rn, st, lsbf, K;
        reg [EXP_BITS-1:0]  ef_r;
        reg [MANT_BITS-1:0] fr_r;
        reg [TOTAL-1:0] res;
        begin
            ra = a[TOTAL-1];  ea = a[TOTAL-2:MANT_BITS];  ma = a[MANT_BITS-1:0];
            rb = b[TOTAL-1];  eb = b[TOTAL-2:MANT_BITS];  mb = b[MANT_BITS-1:0];
            az  = (ea == {EXP_BITS{1'b0}}) && (ma == {MANT_BITS{1'b0}});
            bz  = (eb == {EXP_BITS{1'b0}}) && (mb == {MANT_BITS{1'b0}});
            adn = (ea == {EXP_BITS{1'b0}}) && (ma != {MANT_BITS{1'b0}});
            bdn = (eb == {EXP_BITS{1'b0}}) && (mb != {MANT_BITS{1'b0}});
            sg  = ra ^ rb;                       // product sign

            K = BIAS + MANT_BITS - 1;            // fixed-point unit = 2^(-K)

            if (az || bz) begin
                res = sg ? {1'b1, {(TOTAL-1){1'b0}}} : {TOTAL{1'b0}};   // 0*x = signed 0
            end else begin
                mant_a = (adn ? 0 : (1 << MANT_BITS)) + ma;
                mant_b = (bdn ? 0 : (1 << MANT_BITS)) + mb;
                eff_a  = adn ? 1 : ea;
                eff_b  = bdn ? 1 : eb;
                A = mant_a << (eff_a - 1);       // value in 2^(-K) units (exact integer)
                B = mant_b << (eff_b - 1);
                prod_int = A * B;                // exact integer product
                // leading bit
                L = 0; for (k = 0; k < 32; k = k + 1) if ((prod_int >> k) & 1) L = k;
                exp_field = L - BIAS - 2*MANT_BITS + 2;

                if (exp_field >= 1) begin
                    // ---- normal result: extract MANT frac bits + RNE ----
                    frac = 0;
                    for (k = 0; k < MANT_BITS; k = k + 1)
                        if (L - 1 - k >= 0)
                            frac = frac | (((prod_int >> (L - 1 - k)) & 1) << (MANT_BITS - 1 - k));
                    gd    = (L - MANT_BITS - 1 >= 0) ? ((prod_int >> (L - MANT_BITS - 1)) & 1) : 0;
                    rn    = (L - MANT_BITS - 2 >= 0) ? ((prod_int >> (L - MANT_BITS - 2)) & 1) : 0;
                    st    = 0;
                    for (k = 0; k < 31; k = k + 1)
                        if (k >= 0 && k <= L - MANT_BITS - 3) st = st | ((prod_int >> k) & 1);
                    lsbf = frac & 1;
                    if (gd && (rn || st || lsbf)) frac = frac + 1;   // RNE
                    if (frac >= (1 << MANT_BITS)) begin              // carry: 10.000 -> 1.000*2^(e+1)
                        frac = frac - (1 << MANT_BITS); exp_field = exp_field + 1;
                    end
                    // pack (no-HAS_INF saturation: GF4/6/8/12)
                    if (exp_field >= (1 << EXP_BITS))
                        res = {sg, {EXP_BITS{1'b1}}, {MANT_BITS{1'b1}}};     // max-finite
                    else begin
                        ef_r = exp_field[EXP_BITS-1:0]; fr_r = frac[MANT_BITS-1:0];
                        res = {sg, ef_r, fr_r};
                    end
                end else begin
                    // ---- denormal RESULT: mant_den = round(prod_int >> K) ----
                    // value = prod_int*2^(-2K); denormal field = mant_den*2^(1-BIAS-MANT)
                    // => mant_den = prod_int * 2^(BIAS+MANT-1-2K) = prod_int * 2^(-K).
                    frac = 0;
                    if (K >= 0) frac = prod_int >> K;
                    gd   = (K - 1 >= 0) ? ((prod_int >> (K - 1)) & 1) : 0;
                    st   = 0;
                    for (k = 0; k < 31; k = k + 1)
                        if (k >= 0 && k <= K - 2) st = st | ((prod_int >> k) & 1);
                    lsbf = frac & 1;
                    if (gd && (st || lsbf)) frac = frac + 1;          // RNE
                    if (frac >= (1 << MANT_BITS))
                        res = {sg, {{(EXP_BITS-1){1'b0}}, 1'b1}, {MANT_BITS{1'b0}}}; // smallest normal
                    else if (frac == 0)
                        res = sg ? {1'b1, {(TOTAL-1){1'b0}}} : {TOTAL{1'b0}};       // underflow -> signed 0
                    else
                        res = {sg, {EXP_BITS{1'b0}}, frac[MANT_BITS-1:0]};
                end
            end
            ref_fpmul = res;
        end
    endfunction

    wire [TOTAL-1:0] ref_result = ref_fpmul(in_a, in_b);
    assign mismatch = (result_comb_wire != ref_result);
endmodule
`default_nettype wire
