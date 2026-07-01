// SPDX-License-Identifier: Apache-2.0
// int32_decode — signed 32-bit integer identity decode (int32 = 32-bit, no extension).
`default_nettype none
`timescale 1ns / 1ps
module int32_decode (
    input  wire [31:0] int32_in,
    output wire [31:0] int32_out,
    output wire        is_zero
);
    assign int32_out = int32_in;  // identity (int32 is already 32-bit)
    assign is_zero   = (int32_in == 32'h00000000);
endmodule
`default_nettype wire
