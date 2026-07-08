`default_nettype none
`timescale 1ns / 1ps
// q_format_decode — Q1.15 signed fixed-point → IEEE-754 binary32.
// Value = int16(raw) / 2^15, range [-1.0, 0.99997).
// Fundamentally different from float: no exponent field, pure scaled integer.
module q_format_decode (
    input  wire [15:0] q_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero_o
);
    wire        sign    = q_in[15];
    wire        is_zero = (q_in == 16'd0);
    wire [15:0] absval  = sign ? (~q_in + 16'd1) : q_in;

    function [4:0] clz16;
        input [15:0] v;
        integer i;
        begin
            clz16 = 5'd16;
            for (i = 15; i >= 0; i = i - 1)
                if (v[i] && clz16 == 5'd16) clz16 = 5'd15 - i[4:0];
        end
    endfunction

    wire [4:0]  lzc         = clz16(absval);
    wire [7:0]  biased_exp  = 8'd127 - {3'b0, lzc};
    wire [15:0] norm_shifted = absval << (lzc + 1);
    wire [22:0] fp32_mant   = {norm_shifted, 7'b0};

    assign is_zero_o = is_zero;
    always @(*) begin
        if (is_zero)
            fp32_out = {sign, 31'b0};
        else
            fp32_out = {sign, biased_exp, fp32_mant};
    end
endmodule
`default_nettype none
