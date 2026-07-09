`default_nettype none
`timescale 1ns / 1ps
// pdp11_float_decode — PDP-11 FIS 32-bit float → FP32 decode.
// Format: 1S + 8E (bias 128) + 23M. Hidden bit, IEEE-like.
// Bias 128 vs IEEE-754's 127: decode subtracts 1 from FP32 exponent.
// E=0 (all zeros) → zero or underflow. E=255 → infinity/NaN (PDP-11 reserved).
module pdp11_float_decode (
    input  wire [31:0] pdp11_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero,
    output wire        is_inf,
    output wire        is_nan
);
    wire sign   = pdp11_in[31];
    wire [7:0] exp = pdp11_in[30:23];
    wire [22:0] mant = pdp11_in[22:0];

    assign is_zero = (exp == 8'd0) && (mant == 23'd0);
    assign is_inf  = (exp == 8'd255) && (mant == 23'd0);
    assign is_nan  = (exp == 8'd255) && (mant != 23'd0);

    // Adjust bias: PDP-11 bias 128 → FP32 bias 127, so exp-1
    wire [8:0] exp_adj = {1'b0, exp} - 9'd1;

    always @(*) begin
        if (is_nan)
            fp32_out = {sign, 8'hFF, 23'h400000};
        else if (is_inf)
            fp32_out = {sign, 8'hFF, 23'h000000};
        else if (is_zero)
            fp32_out = {sign, 8'h00, 23'h000000};
        else if (exp == 8'd0)
            // PDP-11 treats E=0 as zero (early models) — flush to zero
            fp32_out = {sign, 8'h00, 23'h000000};
        else if (exp_adj > 9'd254)
            fp32_out = {sign, 8'hFF, 23'h000000}; // overflow → inf
        else if (exp_adj < 9'd1)
            fp32_out = {sign, 8'h00, 23'h000000}; // underflow → zero
        else
            fp32_out = {sign, exp_adj[7:0], mant};
    end
endmodule
`default_nettype wire
