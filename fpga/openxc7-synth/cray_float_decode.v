// SPDX-License-Identifier: Apache-2.0
// cray_float_decode — CRAY-1 64-bit float → FP32.
// 1 sign + 15-bit exp (excess-16384) + 48-bit mantissa (no hidden bit).
// Value = (-1)^S × 2^(E-16384) × mantissa/2^47 (MSB = explicit integer).
`default_nettype none
`timescale 1ns / 1ps
module cray_float_decode (
    input  wire [63:0] cray_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero
);
    wire         sign  = cray_in[63];
    wire [14:0]  exp64 = cray_in[62:48];
    wire [47:0]  mant  = cray_in[47:0];
    assign is_zero = (exp64 == 15'd0) && (mant == 48'd0);

    wire signed [15:0] exp32_raw = $signed({1'b0, exp64}) - 16'sd16384 + 16'sd127;

    wire [22:0] mant_pre = mant[46:24];
    wire        guard    = mant[23];
    wire        round_b  = mant[22];
    wire        sticky   = |mant[21:0];
    wire        round_up = guard & (round_b | sticky | mant_pre[0]);
    wire [23:0] mant_rnd = {1'b0, mant_pre} + (round_up ? 24'd1 : 24'd0);
    wire        mant_carry = mant_rnd[23];

    wire signed [15:0] exp_final = exp32_raw + (mant_carry ? 16'sd1 : 16'd0);

    always @(*) begin
        if (is_zero || exp64 == 15'd0) fp32_out = {sign, 31'd0};
        else if (exp_final > 16'sd254) fp32_out = {sign, 8'hFF, 23'd0};
        else if (exp_final < 16'sd1)   fp32_out = {sign, 31'd0};
        else                           fp32_out = {sign, exp_final[7:0], mant_rnd[22:0]};
    end
endmodule
`default_nettype wire
