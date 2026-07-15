`timescale 1ns / 1ps
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
    input  wire [TOTAL-1:0]        in_a,
    input  wire [TOTAL-1:0]        in_b,
    output wire                    in_ready,
    output reg                     out_valid,
    output reg  [TOTAL-1:0]        out_y,
    input  wire                    out_ready
);
    localparam FRAC_BITS = MANT_BITS + BIAS;
    localparam ACC_WIDTH = 72;
    localparam EXP_MAX = (1 << EXP_BITS) - 1;
    localparam EXP_MAXF = EXP_MAX - 1;

    reg signed [ACC_WIDTH-1:0] acc;
    reg        acc_valid;
    assign in_ready = !in_valid || out_valid;

    wire op_add  = (in_b[1:0] == 2'b00);
    wire op_sub  = (in_b[1:0] == 2'b01);
    wire op_clear = (in_b[1:0] == 2'b10);
    wire op_read = (in_b[1:0] == 2'b11);

    wire sa = in_a[TOTAL-1];
    wire [EXP_BITS-1:0] ea = in_a[TOTAL-2:MANT_BITS];
    wire [MANT_BITS-1:0] ma = in_a[MANT_BITS-1:0];
    wire in_is_zero = (ea == 0) && (ma == 0);
    wire in_is_denorm = (ea == 0) && (ma != 0);
    wire [EXP_BITS:0] ea_eff = in_is_denorm ? 1 : ea;
    wire [MANT_BITS:0] ma_f = in_is_denorm ? {1'b0, ma} : {1'b1, ma};
    wire signed [31:0] exp_unbiased = ea_eff - BIAS;
    wire signed [31:0] shift_amt = exp_unbiased + BIAS;

    reg signed [ACC_WIDTH-1:0] in_fixed;
    always @(*) begin
        in_fixed = 0;
        if (!in_is_zero) begin
            if (shift_amt >= 0 && shift_amt < ACC_WIDTH - MANT_BITS - 1)
                in_fixed = $signed({{(ACC_WIDTH-MANT_BITS-1){1'b0}}, ma_f}) <<< shift_amt;
            else if (shift_amt < 0 && shift_amt > -(ACC_WIDTH - MANT_BITS))
                in_fixed = $signed({{(ACC_WIDTH-MANT_BITS-1){1'b0}}, ma_f}) >>> (-shift_amt);
            else if (shift_amt >= ACC_WIDTH - MANT_BITS - 1)
                in_fixed = {1'b0, {(ACC_WIDTH-1){1'b1}}};
            if (sa ^ op_sub) in_fixed = -in_fixed;
        end
    end

    reg [TOTAL-1:0] result_packed;
    reg [ACC_WIDTH-1:0] flush_abs;
    reg [31:0] flush_lz;
    reg signed [31:0] flush_exp_raw;
    reg [EXP_BITS:0] flush_exp_field;
    reg [MANT_BITS+5:0] flush_mant;
    integer fi;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            acc <= 0; acc_valid <= 0; out_valid <= 0; out_y <= 0;
        end else begin
            out_valid <= 0;
            if (in_valid) begin
                if (op_clear) begin
                    acc <= 0; acc_valid <= 0;
                end else if (op_add || op_sub) begin
                    if (!acc_valid) begin
                        acc <= in_fixed; acc_valid <= 1;
                    end else begin
                        acc <= acc + in_fixed;
                    end
                end

                if (op_read || op_clear) begin
                    if (!acc_valid || (acc == 0)) begin
                        result_packed = {TOTAL{1'b0}};
                    end else begin
                        flush_abs = acc[ACC_WIDTH-1] ? (~acc + 1'b1) : acc;
                        flush_lz = 0;
                        for (fi = ACC_WIDTH-1; fi >= 0; fi = fi - 1)
                            if (flush_abs[fi] && flush_lz == 0)
                                flush_lz = fi;
                        flush_exp_raw = flush_lz - FRAC_BITS;
                        flush_exp_field = flush_exp_raw + BIAS;
                        if (flush_lz > MANT_BITS)
                            flush_mant = flush_abs >> (flush_lz - MANT_BITS);
                        else
                            flush_mant = flush_abs << (MANT_BITS + 1 - flush_lz);
                        if (flush_exp_field >= EXP_MAX) begin
                            if (HAS_INF)
                                result_packed = {acc[ACC_WIDTH-1], EXP_MAX[EXP_BITS-1:0], {MANT_BITS{1'b0}}};
                            else
                                result_packed = {acc[ACC_WIDTH-1], EXP_MAXF[EXP_BITS-1:0], {MANT_BITS{1'b1}}};
                        end else if (flush_exp_field == 0 || $signed(flush_exp_field) < 0) begin
                            result_packed = {TOTAL{1'b0}};
                        end else begin
                            result_packed = {acc[ACC_WIDTH-1], flush_exp_field[EXP_BITS-1:0], flush_mant[MANT_BITS-1:0]};
                        end
                    end
                    out_y <= result_packed;
                    out_valid <= 1;
                end
            end
        end
    end
endmodule
