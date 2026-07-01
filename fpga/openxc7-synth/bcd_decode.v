// SPDX-License-Identifier: Apache-2.0
// Copied from gHashTag/tt-trinity-corona / src/rtl/bcd_decode.v (separate repo,
// NOT a submodule of trinity-fpga — fetched via gh api 2026-07-01).
// 2-digit packed BCD -> 7-bit binary decode.
// bcd_in = {tens[7:4], ones[3:0]}, bin_out = tens*10 + ones (0..99).
// valid = 1 only when both nibbles are 0..9.

`default_nettype none
`timescale 1ns / 1ps

module bcd_decode (
    input  wire [7:0] bcd_in,
    output wire [6:0] bin_out,
    output wire       valid
);

    wire [3:0] tens = bcd_in[7:4];
    wire [3:0] ones = bcd_in[3:0];

    // tens * 10 = (tens << 3) + (tens << 1)
    wire [6:0] tens_x10 = {tens, 3'b0} + {2'b0, tens, 1'b0};

    assign bin_out = tens_x10[6:0] + {3'b0, ones};

    // Valid if both nibbles are 0-9
    assign valid = (tens <= 4'd9) && (ones <= 4'd9);

endmodule

`default_nettype wire
