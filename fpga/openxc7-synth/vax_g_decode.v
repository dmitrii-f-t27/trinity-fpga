// SPDX-License-Identifier: Apache-2.0
// vax_g_decode — DEC VAX G_floating (64-bit) -> FP32 decode.
// VAX G = sign + 11-bit exp (excess-1024) + 52-bit mantissa.
// Decode exp = exp64 - 897 (vs binary64 -896; excess-1024 -> excess-127).
// RNE narrowing of the 52-bit mantissa to 23-bit, identical to binary64.
//
// VAX has NO inf/nan sentinel exponent (unlike IEEE binary64): exp 0..2047 are
// all normal/reserved. exp==0 -> signed zero (true zero / reserved operand);
// overflow (exp_final > 254) saturates to FP32 inf; underflow -> signed zero.
`default_nettype none
`timescale 1ns / 1ps
module vax_g_decode (
    input  wire [63:0] vax_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero
);
    wire         sign  = vax_in[63];
    wire [10:0]  exp64 = vax_in[62:52];   // excess-1024
    wire [51:0] mant64 = vax_in[51:0];
    assign is_zero = (exp64 == 11'd0) && (mant64 == 52'd0);

    // FP32 exp (excess-127) = exp64 - 1024 + 127 = exp64 - 897
    wire signed [11:0] exp32_raw = $signed({1'b0, exp64}) - 12'sd897;

    // RNE: top 23 mantissa bits + guard/round/sticky from bits [28:0]
    wire [22:0] mant_pre  = mant64[51:29];
    wire        guard     = mant64[28];
    wire        round_b   = mant64[27];
    wire        sticky    = |mant64[26:0];
    wire        round_up  = guard & (round_b | sticky | mant_pre[0]);
    wire [23:0] mant_rnd  = {1'b0, mant_pre} + (round_up ? 24'd1 : 24'd0);
    wire        mant_carry = mant_rnd[23];
    wire [22:0] mant_final  = mant_rnd[22:0];
    wire signed [11:0] exp_final = exp32_raw + (mant_carry ? 12'sd1 : 12'sd0);

    always @(*) begin
        if (is_zero || exp64 == 11'd0)      fp32_out = {sign, 31'd0};        // zero / reserved operand
        else if (exp_final > 12'sd254)      fp32_out = {sign, 8'hFF, 23'd0}; // overflow -> FP32 inf
        else if (exp_final < 12'sd1)        fp32_out = {sign, 31'd0};        // underflow -> 0
        else                                fp32_out = {sign, exp_final[7:0], mant_final};
    end
endmodule
`default_nettype wire
