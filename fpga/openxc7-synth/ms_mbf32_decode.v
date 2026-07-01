// SPDX-License-Identifier: Apache-2.0
// ms_mbf32_decode — Microsoft Binary Format (32-bit) -> FP32 decode.
// MBF32 = IEEE FP32 with excess-129 bias (vs IEEE 127). Decode = exp_field - 2.
`default_nettype none
`timescale 1ns / 1ps
module ms_mbf32_decode (
    input  wire [31:0] mbf_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero
);
    assign is_zero = (mbf_in == 32'h00000000);
    wire        sign      = mbf_in[31];
    wire [7:0]  exp_field = mbf_in[30:23];   // excess-129
    wire [22:0] mantissa  = mbf_in[22:0];
    always @(*) begin
        if (is_zero)         fp32_out = 32'h00000000;
        else if (exp_field <= 8'd2) fp32_out = {sign, 31'd0};               // underflow
        else                fp32_out = {sign, exp_field - 8'd2, mantissa};   // bias: -129 -> -127
    end
endmodule
`default_nettype wire
