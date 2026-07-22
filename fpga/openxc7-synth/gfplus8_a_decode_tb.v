// SPDX-License-Identifier: Apache-2.0
// Тестбенч gfplus8_a_decode: дамп decode для каждого (pocket, word) в hex → сверка с Python.
`default_nettype none
`timescale 1ns / 1ps
module tb;
    reg  [7:0]  word;
    reg  [1:0]  pocket;
    wire [31:0] fp32;
    wire        zero;
    integer p, w;
    gfplus8_a_decode dut(.word_in(word), .pocket(pocket), .fp32_out(fp32), .is_zero(zero));
    initial begin
        for (p = 0; p < 4; p = p + 1) begin
            for (w = 0; w < 256; w = w + 1) begin
                pocket = p[1:0]; word = w[7:0]; #1;
                $display("%0d %0d %08x %0d", p, w, fp32, zero);
            end
        end
        $finish;
    end
endmodule
`default_nettype wire
