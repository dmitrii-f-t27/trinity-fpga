// SPDX-License-Identifier: Apache-2.0
// binary64_decode — IEEE 754 binary64 (FP64/double) -> FP32 decode (narrowing with RNE).
// Extract sign + 11-bit exp (excess-1023) + 52-bit mantissa → 8-bit exp (excess-127) + 23-bit mantissa.
// RNE rounding: guard/round/sticky from the 29 dropped mantissa bits.
`default_nettype none
`timescale 1ns / 1ps
module binary64_decode (
    input  wire [63:0] fp64_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero
);
    wire         sign  = fp64_in[63];
    wire [10:0]  exp64 = fp64_in[62:52];   // excess-1023
    wire [51:0]  mant64 = fp64_in[51:0];
    assign is_zero = (exp64 == 11'd0) && (mant64 == 52'd0);

    wire is_inf = (exp64 == 11'h7FF) && (mant64 == 0);
    wire is_nan = (exp64 == 11'h7FF) && (mant64 != 0);

    // FP32 exp = exp64 - 1023 + 127 = exp64 - 896
    wire signed [11:0] exp32_raw = $signed({1'b0, exp64}) - 12'sd896;

    // RNE: top 23 bits + guard/round/sticky from bits [28:0]
    wire [22:0] mant_pre  = mant64[51:29];
    wire        guard      = mant64[28];
    wire        round_b   = mant64[27];
    wire        sticky    = |mant64[26:0];
    wire        round_up  = guard & (round_b | sticky | mant_pre[0]);
    wire [23:0] mant_rnd  = {1'b0, mant_pre} + (round_up ? 24'd1 : 24'd0);
    wire        mant_carry = mant_rnd[23];
    wire [22:0] mant_final  = mant_rnd[22:0];
    wire signed [11:0] exp_final = exp32_raw + (mant_carry ? 12'sd1 : 12'sd0);

    always @(*) begin
        if (is_zero || exp64 == 11'd0)
            fp32_out = {sign, 31'd0};
        else if (is_nan)
            fp32_out = {sign, 8'hFF, 23'h400000};
        else if (is_inf || exp_final > 12'sd254)
            fp32_out = {sign, 8'hFF, 23'd0};
        else if (exp_final < 12'sd1)
            fp32_out = {sign, 31'd0};
        else
            fp32_out = {sign, exp_final[7:0], mant_final};
    end
endmodule
`default_nettype wire
