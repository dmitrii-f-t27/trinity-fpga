// SPDX-License-Identifier: Apache-2.0
// ibm_hfp128_decode — IBM hexadecimal floating-point (128-bit) → FP32.
// 1 sign + 7-bit exp (excess-64, base-16) + 120-bit fraction.
// Value = (-1)^S × 16^(E-64) × fraction/2^120 = (-1)^S × 2^(4*(E-64)-120) × fraction.
`default_nettype none
`timescale 1ns / 1ps
module ibm_hfp128_decode (
    input  wire [127:0] ibm_in,
    output reg  [31:0]  fp32_out,
    output wire         is_zero
);
    wire         sign      = ibm_in[127];
    wire [6:0]   exp_field = ibm_in[126:120];
    wire [119:0] fraction  = ibm_in[119:0];
    assign is_zero = (exp_field == 7'd0) && (fraction == 120'd0);

    // Leading-1 in 120-bit fraction (find highest set bit)
    integer i;
    reg [6:0] lead;
    always @(*) begin
        lead = 7'd0;
        for (i = 0; i < 120; i = i + 1)
            if (fraction[i]) lead = i[6:0];
    end

    // exp_base2 = 4*(E-64) - 120; exp_final = exp_base2 + lead + 127
    wire signed [14:0] exp_calc   = $signed({8'd0, exp_field}) - 15'sd64;
    wire signed [14:0] exp_base2  = (exp_calc <<< 2) - 15'sd120;
    wire signed [14:0] exp_final  = exp_base2 + $signed({8'd0, lead}) + 15'sd127;

    // Align leading-1 to bit 119; take 23 bits below it
    wire [119:0] fsh = fraction << (7'd119 - lead);
    wire [22:0]  mant = fsh[118:96];

    always @(*) begin
        if (is_zero || fraction == 120'd0) fp32_out = {sign, 31'd0};
        else if (exp_final > 15'sd254)     fp32_out = {sign, 8'hFF, 23'd0};
        else if (exp_final < 15'sd1)       fp32_out = {sign, 31'd0};
        else                               fp32_out = {sign, exp_final[7:0], mant};
    end
endmodule
`default_nettype wire
