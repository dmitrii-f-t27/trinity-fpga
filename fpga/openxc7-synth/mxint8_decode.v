// SPDX-License-Identifier: Apache-2.0
// Copied from gHashTag/tt-trinity-corona / src/rtl/mxint8_decode.v (separate repo,
// NOT a submodule of trinity-fpga — fetched via gh api 2026-07-01).
// MXINT8 -> FP32 decode. OCP MX 8-bit integer with implicit 2^(-6) scale.
// Value = int8_val * 2^(-6). Range: [-127/64, +127/64]. -128 reserved (NaN).

`default_nettype none
`timescale 1ns / 1ps

module mxint8_decode (
    input  wire [7:0]  mxint8_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero,
    output wire        is_reserved
);

    assign is_zero     = (mxint8_in == 8'h00);
    assign is_reserved = (mxint8_in == 8'h80);

    wire       sign    = mxint8_in[7];
    wire [6:0] abs_val = sign ? (~mxint8_in[6:0] + 7'd1) : mxint8_in[6:0];

    reg [2:0] lop; // leading-one position in abs_val (0-6)
    always @(*) begin
        casez (abs_val)
            7'b1??????: lop = 3'd6;
            7'b01?????: lop = 3'd5;
            7'b001????: lop = 3'd4;
            7'b0001???: lop = 3'd3;
            7'b00001??: lop = 3'd2;
            7'b000001?: lop = 3'd1;
            7'b0000001: lop = 3'd0;
            default:    lop = 3'd0;
        endcase
    end

    // FP32 exponent = 127 + (lop - 6) = 121 + lop
    wire [7:0] fp32_exp = 8'd121 + {5'b0, lop};

    // FP32 mantissa: strip leading 1, left-align to 23 bits
    reg [22:0] fp32_mant;
    always @(*) begin
        case (lop)
            3'd6: fp32_mant = {abs_val[5:0], 17'b0};
            3'd5: fp32_mant = {abs_val[4:0], 18'b0};
            3'd4: fp32_mant = {abs_val[3:0], 19'b0};
            3'd3: fp32_mant = {abs_val[2:0], 20'b0};
            3'd2: fp32_mant = {abs_val[1:0], 21'b0};
            3'd1: fp32_mant = {abs_val[0],   22'b0};
            3'd0: fp32_mant = 23'b0;
            default: fp32_mant = 23'b0;
        endcase
    end

    always @(*) begin
        if (is_zero)
            fp32_out = 32'h00000000;
        else if (is_reserved)
            fp32_out = 32'h7FC00000; // NaN for reserved -128
        else
            fp32_out = {sign, fp32_exp, fp32_mant};
    end

endmodule

`default_nettype wire
