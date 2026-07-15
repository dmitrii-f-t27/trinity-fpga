`timescale 1ns / 1ps
// ============================================================================
// gf_quire_param.v — Parameterized extended-precision ACCUMULATOR (quire).
// AXI-Stream interface: accumulates in_a into internal wide register.
// in_b selects operation: 0=ADD, 1=SUBTRACT, 2=CLEAR+READ, 3=READ only.
// Uses 64-bit accumulator (sign + 11-bit exp + 52-bit mantissa = binary64-like).
// Output is rounded to TOTAL-bit format on READ.
// ============================================================================
module gf_quire_param #(
    parameter EXP_BITS  = 8,
    parameter MANT_BITS = 23,
    parameter TOTAL     = 1 + EXP_BITS + MANT_BITS,
    parameter BIAS      = (1 << (EXP_BITS - 1)) - 1,
    parameter HAS_INF   = 1
)(
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    in_valid,
    input  wire [TOTAL-1:0]        in_a,    // value to accumulate
    input  wire [TOTAL-1:0]        in_b,    // [1:0] = op: 0=add, 1=sub, 2=clear, 3=read
    output wire                    in_ready,
    output reg                     out_valid,
    output reg  [TOTAL-1:0]        out_y,
    input  wire                    out_ready
);
    // 64-bit accumulator: {sign(1), exp(11), mant(52)} = binary64 format
    reg [63:0] acc;
    reg        acc_valid;

    localparam EXP_MAX = (1 << EXP_BITS) - 1;
    localparam EXP_MAXF = EXP_MAX - 1;

    assign in_ready = !in_valid || out_valid;  // simple handshake

    wire op_add  = (in_b[1:0] == 2'b00);
    wire op_sub  = (in_b[1:0] == 2'b01);
    wire op_clear = (in_b[1:0] == 2'b10);
    wire op_read = (in_b[1:0] == 2'b11);

    // Convert TOTAL-bit input to binary64 for accumulation
    // Simple approach: sign-extend exponent, zero-extend mantissa
    wire sa = in_a[TOTAL-1];
    wire [EXP_BITS-1:0] ea = in_a[TOTAL-2:MANT_BITS];
    wire [MANT_BITS-1:0] ma = in_a[MANT_BITS-1:0];

    // Check for special inputs
    wire in_is_zero = (ea == 0) && (ma == 0);
    wire in_is_nan  = HAS_INF && (ea == EXP_MAX) && (ma != 0);

    // Convert to binary64-like (wider exponent and mantissa)
    // For fp32 input: exp32 = ea, adjust to binary64 bias (1023 vs 127)
    wire signed [12:0] exp_adj = $signed({1'b0, ea}) - BIAS + 1023;  // to binary64 bias
    wire [63:0] in_b64 = {sa, exp_adj[10:0], ma, {(52-MANT_BITS){1'b0}}};

    // For subtraction: flip sign
    wire [63:0] in_b64_eff = op_sub ? {~in_b64[63], in_b64[62:0]} : in_b64;

    // Convert accumulator back to TOTAL-bit format for output
    reg [TOTAL-1:0] result_packed;

    // Extract from binary64-like format (module-level wires)
    wire acc_sign = acc[63];
    wire [10:0] acc_exp = acc[62:52];
    wire [51:0] acc_mant = acc[51:0];
    wire signed [12:0] tgt_exp = $signed({1'b0, acc_exp}) - 1023 + BIAS;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            acc <= 64'b0;
            acc_valid <= 0;
            out_valid <= 0;
            out_y <= 0;
        end else begin
            out_valid <= 0;
            if (in_valid) begin
                if (op_clear) begin
                    acc <= 64'b0;
                    acc_valid <= 0;
                end else if (op_add || op_sub) begin
                    if (!acc_valid) begin
                        acc <= in_is_nan ? 64'b0 : (in_is_zero ? 64'b0 : in_b64_eff);
                        acc_valid <= 1;
                    end else begin
                        if (!in_is_zero && !in_is_nan)
                            acc <= acc + in_b64_eff;
                    end
                end

                if (op_read || op_clear) begin
                    if (!acc_valid || (acc == 64'b0)) begin
                        result_packed <= {TOTAL{1'b0}};
                    end else begin
                        if (tgt_exp >= EXP_MAX) begin
                            if (HAS_INF)
                                result_packed <= {acc_sign, EXP_MAX[EXP_BITS-1:0], {MANT_BITS{1'b0}}};
                            else
                                result_packed <= {acc_sign, EXP_MAXF[EXP_BITS-1:0], {MANT_BITS{1'b1}}};
                        end else if (tgt_exp <= 0) begin
                            result_packed <= {acc_sign, {TOTAL-1{1'b0}}};
                        end else begin
                            result_packed <= {acc_sign, tgt_exp[EXP_BITS-1:0], acc_mant[51:52-MANT_BITS]};
                        end
                    end
                    out_y <= result_packed;
                    out_valid <= 1;
                end
            end
        end
    end
endmodule
