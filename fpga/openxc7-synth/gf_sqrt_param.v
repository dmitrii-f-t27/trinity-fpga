`timescale 1ns / 1ps
// ============================================================================
// gf_sqrt_param.v — Parameterized floating-point SQUARE ROOT.
// AXI-Stream interface matching gf_adder_param / gf_mul_param / gf_div_param.
// Algorithm: exponent halving + mantissa Newton-Raphson (2 iterations).
//   sqrt(sign,exp,mant): sign must be 0 (negative → NaN), exp halved,
//   mantissa via Newton-Raphson: x_{n+1} = (x_n + a/x_n) / 2
// Multi-cycle: 2 NR iterations using gf_div_param + gf_adder_param.
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
    input  wire [TOTAL-1:0]        in_b,    // unused, kept for interface compat
    output wire                    in_ready,
    output reg                     out_valid,
    output reg  [TOTAL-1:0]        out_y,
    input  wire                    out_ready
);
    // Field extraction from in_a
    wire                        sa = in_a[TOTAL-1];
    wire [EXP_BITS-1:0]         ea = in_a[TOTAL-2:MANT_BITS];
    wire [MANT_BITS-1:0]        ma = in_a[MANT_BITS-1:0];

    localparam EXP_MAX = (1 << EXP_BITS) - 1;
    localparam EXP_MAXF = EXP_MAX - 1;

    // Special detection
    wire a_is_zero = (ea == 0) && (ma == 0);
    wire a_is_inf  = HAS_INF && (ea == EXP_MAX) && (ma == 0);
    wire a_is_nan  = HAS_INF && (ea == EXP_MAX) && (ma != 0);
    wire is_neg    = sa && !a_is_zero;

    // Result exponent: (ea - BIAS) / 2 + BIAS
    // Use signed arithmetic with rounding for odd exponents
    wire signed [22:0] exp_half = $signed({1'b0, ea}) - BIAS;
    wire [22:0] exp_result_raw = (exp_half >> 1) + BIAS;

    // For odd exponent: mantissa needs *0.5 adjustment
    wire exp_is_odd = exp_half[0];

    // Newton-Raphson mantissa sqrt
    // Initial: 1.mantissa. If exp odd, divide by 2 → shift right.
    // NR: x_{n+1} = (x_n + a/x_n) / 2
    // Use behavioral description for synthesis

    localparam IDLE = 3'd0, INIT = 3'd1, NR1 = 3'd2, NR2 = 3'd3, DONE = 3'd4;
    reg [2:0] state;
    reg [MANT_BITS+1:0] a_mant;   // 1.mantissa with guard
    reg [MANT_BITS+1:0] x_est;    // current sqrt estimate
    reg [47:0] div_result;        // a/x temporary
    reg [47:0] add_result;        // (x + a/x)/2 temporary

    assign in_ready = (state == IDLE);

    // Combinational NR step: next_x = (x + a/x) / 2
    // For synthesis, use behavioral * and /
    wire [47:0] a_over_x = a_mant * (1 << MANT_BITS) / x_est;  // fixed-point divide
    wire [47:0] sum_x = x_est + a_over_x;
    wire [MANT_BITS+1:0] next_x = sum_x[MANT_BITS+2:1];  // divide by 2 = shift right 1

    // Result packing
    reg [TOTAL-1:0] result_packed;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            state <= IDLE;
            out_valid <= 0;
            out_y <= 0;
            a_mant <= 0;
            x_est <= 0;
        end else begin
            out_valid <= 0;
            case (state)
                IDLE: begin
                    if (in_valid) begin
                        // Initialize mantissa
                        if (exp_is_odd) begin
                            a_mant <= {1'b1, ma, 1'b0};  // * 0.5 for odd exp
                        end else begin
                            a_mant <= {1'b1, ma, 1'b0};  // keep in [1.0, 2.0) * 2
                        end
                        // Initial estimate: linear approx sqrt(1+x) ≈ 1 + x/2
                        x_est <= {1'b1, ma[MANT_BITS-1:MANT_BITS-1], {(MANT_BITS){1'b0}}};  // ~1.0-1.5
                        state <= INIT;
                    end
                end
                INIT: begin
                    // NR iteration 1: x1 = (x0 + a/x0) / 2
                    x_est <= next_x;
                    state <= NR1;
                end
                NR1: begin
                    // NR iteration 2: x2 = (x1 + a/x1) / 2
                    x_est <= next_x;
                    state <= NR2;
                end
                NR2: begin
                    // Pack result
                    // Handle special cases
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
                        // Normal: pack with halved exponent
                        begin
                            if (exp_result_raw >= EXP_MAX) begin
                                if (HAS_INF)
                                    result_packed <= {1'b0, EXP_MAX[EXP_BITS-1:0], {MANT_BITS{1'b0}}};
                                else
                                    result_packed <= {1'b0, EXP_MAXF[EXP_BITS-1:0], {MANT_BITS{1'b1}}};
                            end else if (exp_result_raw == 0) begin
                                result_packed <= {TOTAL{1'b0}};
                            end else begin
                                result_packed <= {1'b0, exp_result_raw[EXP_BITS-1:0], x_est[MANT_BITS-1:0]};
                            end
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
