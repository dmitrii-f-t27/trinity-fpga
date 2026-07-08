`default_nettype none
`timescale 1ns / 1ps
// binary256_decode — IEEE 754 binary256 (octuple) → FP32 decode.
// Layout: sign(1) + exponent(19) + mantissa(236), bias = 2^18-1 = 262143.
// Truncates mantissa 236→23 bits. Overflow→Inf, underflow→0.
module binary256_decode (
    input  wire [255:0] b256_in,
    output reg  [31:0]  fp32_out
);
    wire        sign   = b256_in[255];
    wire [18:0] exp_in = b256_in[254:236];
    wire [235:0] mant_in = b256_in[235:0];

    localparam [18:0] EXP_MAX = {19{1'b1}};

    wire is_exp_zero = (exp_in == 19'd0);
    wire is_exp_max  = (exp_in == EXP_MAX);
    wire is_mant_zero = (mant_in == 240'd0);

    wire signed [21:0] fp32_biased = $signed({3'b0, exp_in}) - 22'sd262016;
    wire [22:0] fp32_mant = mant_in[235:213];

    always @(*) begin
        if (is_exp_max && !is_mant_zero)
            fp32_out = 32'h7FC00001;
        else if (is_exp_max && is_mant_zero)
            fp32_out = sign ? 32'hFF800000 : 32'h7F800000;
        else if (is_exp_zero)
            fp32_out = {sign, 31'b0};
        else if (fp32_biased >= 22'sd255)
            fp32_out = sign ? 32'hFF800000 : 32'h7F800000;
        else if (fp32_biased <= 22'sd0)
            fp32_out = {sign, 31'b0};
        else
            fp32_out = {sign, fp32_biased[7:0], fp32_mant};
    end
endmodule
`default_nettype none
