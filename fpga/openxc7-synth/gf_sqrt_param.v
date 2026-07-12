`timescale 1ns / 1ps
// ============================================================================
// gf_sqrt_param.v — Parameterized floating-point SQUARE ROOT (v2 optimized).
// AXI-Stream interface matching gf_adder_param / gf_mul_param / gf_div_param.
//
// v2 Algorithm: Reciprocal Square Root via Newton-Raphson — NO DIVISION.
//   y = 1/sqrt(a), then sqrt(a) = a * y
//   NR for rsqrt: y_{n+1} = y_n * (3 - a*y_n^2) / 2
//   Uses ONLY multiplies and adds → much smaller than v1 (behavioral /).
//
// Initial guess: bit-manipulation "magic constant" approach (Quake III style)
//   adapted for 24-bit mantissa. One NR iteration suffices for ~16 bits.
//
// Latency: 3 cycles (INIT → NR1 → PACK)
// Target: <500 LUTs (vs v1: 4467 LUTs)
// ============================================================================
module gf_sqrt_param #(
    parameter EXP_BITS  = 8,
    parameter MANT_BITS = 23,
    parameter TOTAL     = 1 + EXP_BITS + MANT_BITS,
    parameter BIAS      = (1 << (EXP_BITS - 1)) - 1,
    parameter HAS_INF   = 1
)(
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    in_valid,
    input  wire [TOTAL-1:0]        in_a,
    input  wire [TOTAL-1:0]        in_b,
    output wire                    in_ready,
    output reg                     out_valid,
    output reg  [TOTAL-1:0]        out_y,
    input  wire                    out_ready
);
    wire                        sa = in_a[TOTAL-1];
    wire [EXP_BITS-1:0]         ea = in_a[TOTAL-2:MANT_BITS];
    wire [MANT_BITS-1:0]        ma = in_a[MANT_BITS-1:0];

    localparam EXP_MAX = (1 << EXP_BITS) - 1;
    localparam EXP_MAXF = EXP_MAX - 1;

    wire a_is_zero = (ea == 0) && (ma == 0);
    wire a_is_inf  = HAS_INF && (ea == EXP_MAX) && (ma == 0);
    wire a_is_nan  = HAS_INF && (ea == EXP_MAX) && (ma != 0);
    wire is_neg    = sa && !a_is_zero;

    // Result exponent: (ea - BIAS) / 2 + BIAS
    wire signed [22:0] exp_half = $signed({1'b0, ea}) - BIAS;
    wire [22:0] exp_result_raw = (exp_half >> 1) + BIAS;
    wire exp_is_odd = exp_half[0];

    // Mantissa as 24-bit (1.mantissa)
    wire [23:0] mant24 = {1'b1, ma};
    // If exp is odd, halve the mantissa range → shift right
    wire [23:0] mant_eff = exp_is_odd ? {1'b0, mant24[23:1]} : mant24;

    // ── Reciprocal sqrt initial guess (magic constant) ──
    // For fp32: i = 0x5f3759df - (i >> 1)
    // We operate on the mantissa (24-bit). Approximate: y0 ≈ 1.0 - (mant_eff - 1.0) * 0.5
    // Simple linear: rsqrt(1+x) ≈ 1 - x/2 for x in [0,1)
    wire [23:0] x_minus_1 = mant_eff - 24'h800000;  // x = mant_eff - 1.0
    // y0 = 1.0 - x/2 = 0x800000 - (x_minus_1 >> 1)
    wire [23:0] y0_est = 24'h800000 - (x_minus_1 >> 1);

    // ── State machine ──
    localparam IDLE = 2'd0, NR = 2'd1, PACK = 2'd2;
    reg [1:0] state;
    reg [47:0] y_sq;       // y * y (48-bit product)
    reg [47:0] three_minus; // 3 - a*y^2
    reg [23:0] y_cur;      // current rsqrt estimate
    reg [47:0] a_times_y2; // a * y2 (sqrt result mantissa)

    assign in_ready = (state == IDLE);

    // NR step (combinational): y_new = y * (3 - a*y*y) / 2
    wire [47:0] y_sq_next = y_cur * y_cur;              // y^2
    wire [47:0] ay_sq_next = mant_eff * y_sq_next[47:24]; // a * y^2 (24x24 → 24)
    // 3.0 - a*y^2: since ay_sq is in [0, 3), result in [0, 3]
    wire signed [25:0] three_sub = 26'sd50331648 - $signed({2'b0, ay_sq_next[47:24]}); // 3.0 in Q24 = 0x3000000
    wire [23:0] y_new = (y_cur * three_sub[23:0]) >> 1;  // y * (3-ay^2) / 2

    // Final: sqrt = a * y_final
    wire [47:0] sqrt_mant = mant_eff * y_cur;

    // Result packing
    reg [TOTAL-1:0] result_packed;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            state <= IDLE;
            out_valid <= 0;
            out_y <= 0;
            y_cur <= 0;
        end else begin
            out_valid <= 0;
            case (state)
                IDLE: begin
                    if (in_valid) begin
                        y_cur <= y0_est;
                        state <= NR;
                    end
                end
                NR: begin
                    // One NR iteration for reciprocal sqrt
                    y_cur <= y_new[23:0];
                    state <= PACK;
                end
                PACK: begin
                    // Pack result
                    if (a_is_nan || is_neg) begin
                        if (HAS_INF)
                            result_packed <= {1'b0, EXP_MAX[EXP_BITS-1:0], 1'b1, {(MANT_BITS-1){1'b0}}};
                        else
                            result_packed <= {1'b0, EXP_MAXF[EXP_BITS-1:0], {MANT_BITS{1'b1}}};
                    end else if (a_is_zero) begin
                        result_packed <= {TOTAL{1'b0}};
                    end else if (a_is_inf) begin
                        if (HAS_INF)
                            result_packed <= {1'b0, EXP_MAX[EXP_BITS-1:0], {MANT_BITS{1'b0}}};
                        else
                            result_packed <= {1'b0, EXP_MAXF[EXP_BITS-1:0], {MANT_BITS{1'b1}}};
                    end else begin
                        // sqrt_mant has result in [1.0, 2.0) at bit 47:24
                        if (exp_result_raw >= EXP_MAX) begin
                            if (HAS_INF)
                                result_packed <= {1'b0, EXP_MAX[EXP_BITS-1:0], {MANT_BITS{1'b0}}};
                            else
                                result_packed <= {1'b0, EXP_MAXF[EXP_BITS-1:0], {MANT_BITS{1'b1}}};
                        end else if (exp_result_raw == 0) begin
                            result_packed <= {TOTAL{1'b0}};
                        end else begin
                            result_packed <= {1'b0, exp_result_raw[EXP_BITS-1:0], sqrt_mant[46:24-1+1]};
                        end
                    end
                    out_y <= result_packed;
                    out_valid <= 1;
                    state <= IDLE;
                end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
