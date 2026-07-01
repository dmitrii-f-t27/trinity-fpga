// SPDX-License-Identifier: Apache-2.0
// vax_d_decode — DEC VAX D_floating (64-bit) -> FP32 decode.
// Same bias as vax_f (excess-128) but 55-bit mantissa → FP32 23-bit with RNE rounding.
`default_nettype none
`timescale 1ns / 1ps
module vax_d_decode (
    input  wire [63:0] vax_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero
);
    assign is_zero = (vax_in == 64'h0);
    wire        sign      = vax_in[63];
    wire [7:0]  exp_field = vax_in[62:55];   // excess-128
    wire [54:0] mant      = vax_in[54:0];     // 55-bit (explicit leading 1 at bit 54)
    wire [22:0] mant_pre  = mant[54:32];    // top 23 bits (VAX explicit-1 → FP32 MSB)
    wire        guard     = mant[31];
    wire        round_b   = mant[30];
    wire        sticky    = |mant[29:0];
    wire        round_up  = guard & (round_b | sticky | mant_pre[0]);
    wire [23:0] mant_rnd  = {1'b0, mant_pre} + (round_up ? 24'd1 : 24'd0);
    wire        mant_carry = mant_rnd[23];
    wire [22:0] mant_final  = mant_rnd[22:0];
    wire [8:0]  exp_final  = {1'b0, exp_field} - 9'd1 + (mant_carry ? 9'd1 : 9'd0);
    always @(*) begin
        if (is_zero)              fp32_out = 32'h00000000;
        else if (exp_field <= 8'd1) fp32_out = {sign, 31'd0};
        else if (exp_final > 9'd254) fp32_out = {sign, 8'hFF, 23'd0};
        else                       fp32_out = {sign, exp_final[7:0], mant_final};
    end
endmodule
`default_nettype wire
