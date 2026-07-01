// SPDX-License-Identifier: Apache-2.0
// binary128_decode — IEEE 754 binary128 (quad) -> FP32 decode (narrowing with RNE).
// 1 sign + 15-bit exp (excess-16383) + 112-bit mantissa -> 8-bit exp (excess-127) + 23-bit mantissa.
// FP32 exp = exp128 - 16383 + 127 = exp128 - 16256. RNE guard/round/sticky from the 89 dropped bits.
`default_nettype none
`timescale 1ns / 1ps
module binary128_decode (
    input  wire [127:0] fp128_in,
    output reg  [31:0]  fp32_out,
    output wire         is_zero
);
    wire         sign   = fp128_in[127];
    wire [14:0]  exp128 = fp128_in[126:112];   // excess-16383
    wire [111:0] mant   = fp128_in[111:0];
    assign is_zero = (exp128 == 15'd0) && (mant == 112'd0);

    wire is_inf = (exp128 == 15'h7FFF) && (mant == 112'd0);
    wire is_nan = (exp128 == 15'h7FFF) && (mant != 112'd0);

    // FP32 exp = exp128 - 16256
    wire signed [15:0] exp32_raw = $signed({1'b0, exp128}) - 16'sd16256;

    // RNE: top 23 bits + guard/round/sticky from bits [88:0]
    wire [22:0] mant_pre  = mant[111:89];
    wire        guard     = mant[88];
    wire        round_b   = mant[87];
    wire        sticky    = |mant[86:0];
    wire        round_up  = guard & (round_b | sticky | mant_pre[0]);
    wire [23:0] mant_rnd  = {1'b0, mant_pre} + (round_up ? 24'd1 : 24'd0);
    wire        mant_carry = mant_rnd[23];
    wire [22:0] mant_final  = mant_rnd[22:0];
    wire signed [15:0] exp_final = exp32_raw + (mant_carry ? 16'sd1 : 16'sd0);

    always @(*) begin
        if (is_zero || exp128 == 15'd0)        fp32_out = {sign, 31'd0};
        else if (is_nan)                       fp32_out = {sign, 8'hFF, 23'h400000};
        else if (is_inf || exp_final > 16'sd254) fp32_out = {sign, 8'hFF, 23'd0};
        else if (exp_final < 16'sd1)           fp32_out = {sign, 31'd0};
        else                                   fp32_out = {sign, exp_final[7:0], mant_final};
    end
endmodule
`default_nettype wire
