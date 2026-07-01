// SPDX-License-Identifier: Apache-2.0
// Copied from gHashTag/tt-trinity-corona / src/rtl/e8m0_decode.v (separate repo,
// NOT a submodule of trinity-fpga — fetched via gh api 2026-07-01).
// E8M0 -> FP32 decode. OCP MX shared scale factor: 8-bit exponent-only.
// Value = 2^(e - 127). No sign bit. 0xFF = NaN. 0x00 = 2^(-127).

`default_nettype none
`timescale 1ns / 1ps

module e8m0_decode (
    input  wire [7:0]  e8m0_in,
    output reg  [31:0] fp32_out,
    output wire        is_nan
);

    assign is_nan = (e8m0_in == 8'hFF);

    always @(*) begin
        if (e8m0_in == 8'hFF)
            fp32_out = 32'h7FC00000;
        else if (e8m0_in == 8'h00)
            fp32_out = 32'h00400000; // 2^(-127) as FP32 subnormal
        else
            fp32_out = {1'b0, e8m0_in, 23'b0};
    end

endmodule
`default_nettype wire
