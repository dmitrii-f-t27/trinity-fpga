// SPDX-License-Identifier: Apache-2.0
// INT16 (signed 2's complement) -> 32-bit sign-extended output.
// Mirror of int8_decode.v (tt-trinity-corona) widened to 16-bit input.

`default_nettype none
`timescale 1ns / 1ps

module int16_decode (
    input  wire [15:0] int16_in,
    output wire [31:0] int32_out,
    output wire        is_zero
);

    assign int32_out = {{16{int16_in[15]}}, int16_in};
    assign is_zero   = (int16_in == 16'd0);

endmodule

`default_nettype wire
