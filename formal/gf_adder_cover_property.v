`default_nettype none
`timescale 1ns / 1ps

// =============================================================================
// gf_adder_cover_property.v — REACHABILITY cover for gf_adder_param special cases.
//
// Companion to gf_adder_property.v (bmc proof). Proves that Inf/NaN/0 inputs
// are reachable, ensuring the bmc assert is non-vacuous.
//
// Cover points (8 total, gated on HAS_INF):
//   1. Inf + Inf (same sign) → Inf
//   2. Inf - Inf (diff sign) → qNaN (unique to ADD)
//   3. Inf + finite → Inf
//   4. NaN input → propagation
//   5. Zero + Zero → Zero
//   6. Zero + finite → passthrough
//   7. DUT emits Inf (overflow)
//   8. DUT emits qNaN (Inf-Inf)
//
// PASS = all 8 covers reachable within depth 20.
// =============================================================================

module gf_adder_cover_property #(
    parameter EXP_BITS  = 6,
    parameter MANT_BITS = 9,
    parameter HAS_INF   = 1,
    parameter TOTAL     = 1 + EXP_BITS + MANT_BITS,
    parameter BIAS      = (1 << (EXP_BITS - 1)) - 1
)(
    input wire clk
);

    reg [2:0] rst_cnt;
    initial rst_cnt = 3'b011;
    always @(posedge clk) if (rst_cnt) rst_cnt <= rst_cnt - 3'b001;
    wire rst = |rst_cnt;

    wire [TOTAL-1:0] a_op;
    wire [TOTAL-1:0] b_op;
    assign a_op = $anyconst;
    assign b_op = $anyconst;

    wire             in_valid = 1'b1;
    wire             out_ready = 1'b1;
    wire             in_ready, out_valid;
    wire [TOTAL-1:0] out_y;

    gf_adder_param #(
        .EXP_BITS(EXP_BITS),
        .MANT_BITS(MANT_BITS),
        .HAS_INF(HAS_INF)
    ) dut (
        .clk(clk), .rst(rst),
        .in_valid(in_valid), .in_a(a_op), .in_b(b_op), .in_ready(in_ready),
        .out_valid(out_valid), .out_y(out_y), .out_ready(out_ready)
    );

    reg [2:0] settle;
    initial settle = 3'b000;
    always @(posedge clk) begin
        if (rst) settle <= 3'b000;
        else if (~&settle) settle <= settle + 3'b001;
    end
    wire primed = (~rst) && (&settle);

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

    wire out_exp_all_ones = (out_y[TOTAL-2:MANT_BITS] == {EXP_BITS{1'b1}});
    wire out_mant_zero    = (out_y[MANT_BITS-1:0] == 0);
    wire out_inf  = out_exp_all_ones && out_mant_zero;
    wire out_nan  = out_exp_all_ones && !out_mant_zero;
    wire out_zero = (out_y[TOTAL-2:0] == 0);

    generate
    if (HAS_INF != 0) begin : g_wv_add_cover

        always @(posedge clk) cover(primed && a_inf && b_inf && (sa == sb));
        always @(posedge clk) cover(primed && a_inf && b_inf && (sa != sb));
        always @(posedge clk) cover(primed && a_inf && !b_spec);
        always @(posedge clk) cover(primed && (a_nan || b_nan));
        always @(posedge clk) cover(primed && az && bz);
        always @(posedge clk) cover(primed && az && !b_spec && !bz);
        always @(posedge clk) cover(primed && out_valid && out_inf);
        always @(posedge clk) cover(primed && out_valid && out_nan);

    end else begin : g_wv_add_noinf
        always @(posedge clk) cover(primed && az);
        always @(posedge clk) cover(primed && bz);
        always @(posedge clk) cover(primed && az && bz);
        always @(posedge clk) cover(primed && out_zero);
    end
    endgenerate

endmodule

`default_nettype wire
