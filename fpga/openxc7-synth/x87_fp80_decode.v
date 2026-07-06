// SPDX-License-Identifier: Apache-2.0
// x87_fp80_decode — Intel x87 80-bit extended precision → FP32.
// 1 sign + 15-bit exp (excess-16383) + 64-bit mantissa (EXPLICIT integer bit).
// No hidden bit — the integer part (bit 63) is explicit.
// Pseudo-denormal (exp=0, int=1) handled; pseudo-infinity/NaN (exp=0x7FFF) → NaN.
`default_nettype none
`timescale 1ns / 1ps
module x87_fp80_decode (
    input  wire [79:0] x87_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero
);
    wire        sign   = x87_in[79];
    wire [14:0] exp80  = x87_in[78:64];
    wire [63:0] mant64 = x87_in[63:0];  // bit 63 = explicit integer bit
    wire        int_bit = mant64[63];
    assign is_zero = (exp80 == 15'd0) && (mant64 == 64'd0);

    // Pseudo-Infinity / Pseudo-NaN (exp=0x7FFF) → qNaN
    wire is_pseudo = (exp80 == 15'h7FFF) && !int_bit;

    // FP32 exp = exp80 - 16383 + 127 = exp80 - 16256
    wire signed [15:0] exp32_raw = $signed({1'b0, exp80}) - 16'sd16256;

    // RNE: top 23 mantissa bits (below the explicit integer bit) + guard/round/sticky
    wire [22:0] mant_pre  = mant64[62:40];
    wire        guard     = mant64[39];
    wire        round_b   = mant64[38];
    wire        sticky    = |mant64[37:0];
    wire        round_up  = guard & (round_b | sticky | mant_pre[0]);
    wire [23:0] mant_rnd  = {1'b0, mant_pre} + (round_up ? 24'd1 : 24'd0);
    wire        mant_carry = mant_rnd[23];
    wire [22:0] mant_final = mant_rnd[22:0];
    wire signed [15:0] exp_final = exp32_raw + (mant_carry ? 16'sd1 : 16'sd0);

    always @(*) begin
        if (is_zero)                       fp32_out = {sign, 31'd0};
        else if (is_pseudo || exp80 == 15'h7FFF) fp32_out = 32'h7FC00000; // NaN
        else if (exp_final > 16'sd254)     fp32_out = {sign, 8'hFF, 23'd0};
        else if (exp_final < 16'sd1)       fp32_out = {sign, 31'd0};
        else                               fp32_out = {sign, exp_final[7:0], mant_final};
    end
endmodule
`default_nettype wire
