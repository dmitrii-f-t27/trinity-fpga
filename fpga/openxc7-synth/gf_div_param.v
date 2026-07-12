`timescale 1ns / 1ps
// ============================================================================
// gf_div_param.v — Parameterized floating-point DIVIDER.
// Same AXI-Stream interface as gf_adder_param / gf_mul_param.
// Uses iterative shift-subtract for mantissa division (multi-cycle, 24 iterations).
// Algorithm: sign=sa^sb, exp=ea-eb+BIAS, mant=dividend/divisor via non-restoring.
// Special cases: 0/x=0, x/0=Inf, Inf/Inf=NaN, NaN=NaN.
// ============================================================================
module gf_div_param #(
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
    // Field extraction
    wire                        sa = in_a[TOTAL-1];
    wire [EXP_BITS-1:0]         ea = in_a[TOTAL-2:MANT_BITS];
    wire [MANT_BITS-1:0]        ma = in_a[MANT_BITS-1:0];
    wire                        sb = in_b[TOTAL-1];
    wire [EXP_BITS-1:0]         eb = in_b[TOTAL-2:MANT_BITS];
    wire [MANT_BITS-1:0]        mb = in_b[MANT_BITS-1:0];

    localparam EXP_MAX = (1 << EXP_BITS) - 1;
    localparam EXP_MAXF = EXP_MAX - 1;
    localparam EXP_ZERO = 0;

    // Special detection
    wire a_is_zero = (ea == 0) && (ma == 0);
    wire b_is_zero = (eb == 0) && (mb == 0);
    wire a_is_inf  = HAS_INF && (ea == EXP_MAX) && (ma == 0);
    wire b_is_inf  = HAS_INF && (eb == EXP_MAX) && (mb == 0);
    wire a_is_nan  = HAS_INF && (ea == EXP_MAX) && (ma != 0);
    wire b_is_nan  = HAS_INF && (eb == EXP_MAX) && (mb != 0);

    // Sign
    wire rs = sa ^ sb;

    // Result exponent: ea - eb + BIAS (signed arithmetic)
    wire signed [20:0] exp_raw = $signed({1'b0, ea}) - $signed({1'b0, eb}) + BIAS;

    // Iterative division state machine
    // Dividend = {1, ma} (implicit 1), Divisor = {1, mb}
    // We compute quotient = dividend / divisor, normalized to [1.0, 2.0)
    // Using restoring division: shift dividend left, subtract divisor if >= 0

    localparam IDLE = 2'd0, DIVIDE = 2'd1, FINISH = 2'd2;
    reg [1:0] state;
    reg [MANT_BITS:0] div_rem;      // remainder
    reg [MANT_BITS:0] div_quot;     // quotient being built
    reg [MANT_BITS:0] divisor_r;    // divisor register
    reg [5:0] bit_cnt;              // iteration counter
    reg [20:0] exp_r;
    reg rsign;
    reg [MANT_BITS:0] q_norm_r;
    reg [20:0] e_norm_r;

    assign in_ready = (state == IDLE);

    // Normalization wires (combinational)
    wire [MANT_BITS:0] q_final = div_quot[MANT_BITS] ? div_quot : (div_quot << 1);
    wire signed [21:0] e_raw_final = div_quot[MANT_BITS] ? $signed(exp_r) : ($signed(exp_r) - 1);
    wire [21:0] e_final_clamped = (e_raw_final >= EXP_MAX) ? EXP_MAX :
                                   (e_raw_final <= 0) ? 0 : e_raw_final[21:0];

    // Combinational result packing
    reg [TOTAL-1:0] result_packed;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            state <= IDLE;
            out_valid <= 0;
            out_y <= 0;
            div_rem <= 0;
            div_quot <= 0;
            divisor_r <= 0;
            bit_cnt <= 0;
            exp_r <= 0;
            rsign <= 0;
        end else begin
            out_valid <= 0;
            case (state)
                IDLE: begin
                    if (in_valid) begin
                        rsign <= rs;
                        exp_r <= exp_raw;
                        // Initialize division: dividend in remainder, divisor in register
                        div_rem <= {1'b1, ma};
                        div_quot <= 0;
                        divisor_r <= {1'b1, mb};
                        bit_cnt <= MANT_BITS + 1; // iterate MANT_BITS+1 times
                        state <= DIVIDE;
                    end
                end
                DIVIDE: begin
                    if (bit_cnt > 0) begin
                        // Shift remainder left by 1
                        // Compare with divisor, subtract if >=
                        if ({div_rem[MANT_BITS-1:0], 1'b0} >= divisor_r) begin
                            div_rem <= {div_rem[MANT_BITS-1:0], 1'b0} - divisor_r;
                            div_quot <= {div_quot[MANT_BITS-1:0], 1'b1};
                        end else begin
                            div_rem <= {div_rem[MANT_BITS-1:0], 1'b0};
                            div_quot <= {div_quot[MANT_BITS-1:0], 1'b0};
                        end
                        bit_cnt <= bit_cnt - 1;
                    end else begin
                        state <= FINISH;
                    end
                end
                FINISH: begin
                    // Handle special cases
                    if (a_is_nan || b_is_nan || (a_is_inf && b_is_inf)) begin
                        if (HAS_INF)
                            result_packed <= {1'b0, EXP_MAX[EXP_BITS-1:0], 1'b1, {(MANT_BITS-1){1'b0}}};
                        else
                            result_packed <= {rsign, EXP_MAXF[EXP_BITS-1:0], {MANT_BITS{1'b1}}};
                    end else if (b_is_zero && !a_is_zero) begin
                        if (HAS_INF)
                            result_packed <= {rsign, EXP_MAX[EXP_BITS-1:0], {MANT_BITS{1'b0}}};
                        else
                            result_packed <= {rsign, EXP_MAXF[EXP_BITS-1:0], {MANT_BITS{1'b1}}};
                    end else if (a_is_zero || b_is_inf) begin
                        result_packed <= {rsign, {TOTAL-1{1'b0}}};
                    end else begin
                        // Normal path: normalize quotient and pack
                        // e_final wire computed combinationally
                        result_packed <= {rsign, e_final_clamped[EXP_BITS-1:0], q_final[MANT_BITS-1:0]};
                    end

                    out_y <= result_packed;
                    out_valid <= 1;
                    state <= IDLE;
                end
            endcase
        end
    end
endmodule
