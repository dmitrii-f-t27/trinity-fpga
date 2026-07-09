`default_nettype none
`timescale 1ns / 1ps

// =============================================================================
// gf_mul_cover_property.v — REACHABILITY cover for gf_mul_param special cases.
//
// Companion to gf_mul_property.v (bmc proof). The bmc assert proves
// out_y == ref_fpmul for ALL inputs, but could be vacuously true if the
// solver never reaches Inf/NaN/0 stimulus. This cover module proves that
// special-case inputs ARE reachable by the solver, ensuring the bmc proof
// is non-vacuous for the cases that matter most.
//
// Cover points (8 total, gated on HAS_INF):
//   1. a_inf && b_inf     — Inf × Inf
//   2. a_inf && ~b_spec   — Inf × finite
//   3. a_inf && bz        — Inf × 0 (→ qNaN, unique to MUL)
//   4. b_inf && az        — 0 × Inf (→ qNaN)
//   5. a_nan              — NaN propagation (a side)
//   6. az && ~b_spec      — zero × finite → zero
//   7. DUT emits Inf      — exp_field overflow in numeric path
//   8. DUT emits qNaN     — 0×Inf or NaN input
//
// PASS = all 8 covers reachable within depth 20.
// =============================================================================

module gf_mul_cover_property #(
    parameter EXP_BITS  = 6,    // gf16 default
    parameter MANT_BITS = 9,
    parameter HAS_INF   = 1,
    parameter TOTAL     = 1 + EXP_BITS + MANT_BITS,
    parameter BIAS      = (1 << (EXP_BITS - 1)) - 1
)(
    input wire clk
);

    // ---- Internal synchronous reset (same structure as proof harness) ----
    reg [2:0] rst_cnt;
    initial rst_cnt = 3'b011;
    always @(posedge clk) if (rst_cnt) rst_cnt <= rst_cnt - 3'b001;
    wire rst = |rst_cnt;

    // ---- TIME-INVARIANT free operands ----
    wire [TOTAL-1:0] a_op;
    wire [TOTAL-1:0] b_op;
    assign a_op = $anyconst;
    assign b_op = $anyconst;

    wire             in_valid = 1'b1;
    wire             out_ready = 1'b1;
    wire             in_ready, out_valid;
    wire [TOTAL-1:0] out_y;

    gf_mul_param #(
        .EXP_BITS(EXP_BITS),
        .MANT_BITS(MANT_BITS),
        .HAS_INF(HAS_INF)
    ) dut (
        .clk(clk), .rst(rst),
        .in_valid(in_valid), .in_a(a_op), .in_b(b_op), .in_ready(in_ready),
        .out_valid(out_valid), .out_y(out_y), .out_ready(out_ready)
    );

    // ---- Settle counter ----
    reg [2:0] settle;
    initial settle = 3'b000;
    always @(posedge clk) begin
        if (rst) settle <= 3'b000;
        else if (~&settle) settle <= settle + 3'b001;
    end
    wire primed = (~rst) && (&settle);

    // ---- Decode operand categories ----
    wire sa = a_op[TOTAL-1];
    wire [EXP_BITS-1:0]  ea = a_op[TOTAL-2:MANT_BITS];
    wire [MANT_BITS-1:0] ma = a_op[MANT_BITS-1:0];
    wire sb = b_op[TOTAL-1];
    wire [EXP_BITS-1:0]  eb = b_op[TOTAL-2:MANT_BITS];
    wire [MANT_BITS-1:0] mb = b_op[MANT_BITS-1:0];

    wire az  = (ea == 0) && (ma == 0);
    wire bz  = (eb == 0) && (mb == 0);
    wire a_spec = (HAS_INF != 0) && (ea == {EXP_BITS{1'b1}});
    wire b_spec = (HAS_INF != 0) && (eb == {EXP_BITS{1'b1}});
    wire a_nan  = a_spec && (ma != 0);
    wire b_nan  = b_spec && (mb != 0);
    wire a_inf  = a_spec && (ma == 0);
    wire b_inf  = b_spec && (mb == 0);

    // ---- Decode output categories ----
    wire out_exp_all_ones = (out_y[TOTAL-2:MANT_BITS] == {EXP_BITS{1'b1}});
    wire out_mant_zero    = (out_y[MANT_BITS-1:0] == 0);
    wire out_inf  = out_exp_all_ones && out_mant_zero;
    wire out_nan  = out_exp_all_ones && !out_mant_zero;
    wire out_zero = (out_y[TOTAL-2:0] == 0);

    // ---- Cover points (8 total) ----
    generate
    if (HAS_INF != 0) begin : g_wv_mul_cover

        // 1. Inf × Inf input reachable
        always @(posedge clk) cover(primed && a_inf && b_inf);

        // 2. Inf × finite input reachable
        always @(posedge clk) cover(primed && a_inf && !b_spec);

        // 3. Inf × 0 input reachable (unique MUL special case → qNaN)
        always @(posedge clk) cover(primed && a_inf && bz);

        // 4. 0 × Inf input reachable (symmetric → qNaN)
        always @(posedge clk) cover(primed && az && b_inf);

        // 5. NaN input reachable (propagation)
        always @(posedge clk) cover(primed && (a_nan || b_nan));

        // 6. Zero × finite input reachable
        always @(posedge clk) cover(primed && az && !b_spec && !bz);

        // 7. DUT emits Inf output
        always @(posedge clk) cover(primed && out_valid && out_inf);

        // 8. DUT emits NaN output
        always @(posedge clk) cover(primed && out_valid && out_nan);

    end else begin : g_wv_mul_noinf
        // Non-Inf widths: cover zero and numeric outputs only
        always @(posedge clk) cover(primed && az);
        always @(posedge clk) cover(primed && bz);
        always @(posedge clk) cover(primed && out_zero);
        always @(posedge clk) cover(primed && out_valid && !out_zero);
    end
    endgenerate

endmodule

`default_nettype wire
