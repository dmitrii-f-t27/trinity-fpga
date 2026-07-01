// SPDX-License-Identifier: Apache-2.0
// ms_mbf64_decode — Microsoft Binary Format (64-bit) -> FP32 decode.
// Same structure as vax_d but excess-129 bias (exp - 2). 55-bit mantissa → FP32 23-bit RNE.
`default_nettype none
`timescale 1ns / 1ps
module ms_mbf64_decode (
    input  wire [63:0] mbf_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero
);
    assign is_zero = (mbf_in == 64'h0);
    wire        sign      = mbf_in[63];
    wire [7:0]  exp_field = mbf_in[62:55];   // excess-129
    wire [54:0] mant      = mbf_in[54:0];
    wire [22:0] mant_pre   = mant[54:32];     // top 23 bits (explicit-1 → FP32 MSB)
    wire        guard     = mant[31];
    wire        round_b   = mant[30];
    wire        sticky    = |mant[29:0];
    wire        round_up  = guard & (round_b | sticky | mant_pre[0]);
    wire [23:0] mant_rnd  = {1'b0, mant_pre} + (round_up ? 24'd1 : 24'd0);
    wire        mant_carry = mant_rnd[23];
    wire [22:0] mant_final  = mant_rnd[22:0];
    wire [8:0]  exp_final  = {1'b0, exp_field} - 9'd2 + (mant_carry ? 9'd1 : 9'd0);
    always @(*) begin
        if (is_zero)               fp32_out = 32'h00000000;
        else if (exp_field <= 8'd2) fp32_out = {sign, 31'd0};
        else if (exp_final > 9'd254) fp32_out = {sign, 8'hFF, 23'd0};
        else                        fp32_out = {sign, exp_final[7:0], mant_final};
    end
endmodule
`default_nettype wire
