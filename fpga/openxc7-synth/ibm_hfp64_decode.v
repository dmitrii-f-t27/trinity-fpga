// SPDX-License-Identifier: Apache-2.0
// ibm_hfp64_decode — IBM hexadecimal floating-point (64-bit, HFP double) -> FP32 decode.
// Format: 1 sign + 7-bit exp (excess-64, base-16) + 56-bit fraction (hex 0.MMMMMM...).
// Value = (-1)^S × 16^(E-64) × fraction/2^56 = (-1)^S × 2^(4*(E-64)-56) × fraction.
// Normalize: leading-1 detect + barrel shift to 23-bit FP32 mantissa (truncate — matches ibm_hfp32 policy).
`default_nettype none
`timescale 1ns / 1ps
module ibm_hfp64_decode (
    input  wire [63:0] ibm_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero
);
    wire        sign       = ibm_in[63];
    wire [6:0]  exp_field  = ibm_in[62:56];  // excess-64, base-16
    wire [55:0] fraction   = ibm_in[55:0];   // 56-bit hex fraction 0.MMMM...
    assign is_zero = (exp_field == 7'd0) && (fraction == 56'd0);

    integer i;
    reg [5:0] lead;  // leading-1 position in the 56-bit fraction (0..55)
    always @(*) begin
        lead = 6'd0;
        for (i = 0; i < 56; i = i + 1)
            if (fraction[i]) lead = i[5:0];   // last (highest) set bit wins
    end

    // FP32 exponent = 4*(E-64) - 56 + lead + 127
    wire signed [12:0] exp_calc  = $signed({6'd0, exp_field}) - 13'sd64;     // E-64
    wire signed [12:0] exp_base2 = (exp_calc <<< 2) - 13'sd56;               // 4*(E-64) - 56
    wire signed [12:0] exp_final = exp_base2 + $signed({7'd0, lead}) + 13'sd127;

    // Align leading-1 to bit 55; take the 23 fraction bits immediately below it.
    wire [55:0] fsh = fraction << (6'd55 - lead);
    wire [22:0] mant = fsh[54:32];

    always @(*) begin
        if (is_zero || fraction == 56'd0) fp32_out = {sign, 31'd0};         // zero / unnormalized-zero
        else if (exp_final > 13'sd254)     fp32_out = {sign, 8'hFF, 23'd0}; // overflow -> Inf
        else if (exp_final < 13'sd1)       fp32_out = {sign, 31'd0};        // underflow -> zero
        else                               fp32_out = {sign, exp_final[7:0], mant};
    end
endmodule
`default_nettype wire
