`default_nettype none
`timescale 1ns / 1ps
// x87_48bit_decode — Intel x87 48-bit float → FP32 decode.
// Format: 1S + 8E (bias 128) + 39M = 48 bits. Hidden bit, IEEE-like.
// Wider mantissa than FP32 → RNE rounding to 23-bit.
module x87_48bit_decode (
    input  wire [47:0] x87_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero,
    output wire        is_inf,
    output wire        is_nan
);
    wire sign    = x87_in[47];
    wire [7:0]  exp     = x87_in[46:39];
    wire [38:0] mant    = x87_in[38:0];

    assign is_zero = (exp == 8'd0) && (mant == 39'd0);
    assign is_inf  = (exp == 8'd255) && (mant == 39'd0);
    assign is_nan  = (exp == 8'd255) && (mant != 39'd0);

    wire [8:0] exp_adj = {1'b0, exp} - 9'd1;

    // RNE rounding: 39-bit mantissa → 23-bit
    wire [22:0] mant_pre = mant[38:16];
    wire        guard    = mant[15];
    wire        round_b  = mant[14];
    wire        sticky   = |mant[13:0];
    wire        round_up = guard & (round_b | sticky | mant_pre[0]);
    wire [23:0] mant_rnd = {1'b0, mant_pre} + (round_up ? 24'd1 : 24'd0);
    wire        carry    = mant_rnd[23];
    wire [22:0] mant_fin = mant_rnd[22:0];
    wire [8:0]  exp_fin  = exp_adj + (carry ? 9'd1 : 9'd0);

    always @(*) begin
        if (is_nan)
            fp32_out = {sign, 8'hFF, 23'h400000};
        else if (is_inf)
            fp32_out = {sign, 8'hFF, 23'h000000};
        else if (is_zero)
            fp32_out = {sign, 8'h00, 23'h000000};
        else if (exp == 8'd0)
            fp32_out = {sign, 8'h00, 23'h000000};
        else if (exp_fin > 9'd254)
            fp32_out = {sign, 8'hFF, 23'h000000};
        else if (exp_fin < 9'd1)
            fp32_out = {sign, 8'h00, 23'h000000};
        else
            fp32_out = {sign, exp_fin[7:0], mant_fin};
    end
endmodule
`default_nettype wire
