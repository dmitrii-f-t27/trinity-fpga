// gf16_param_top.v — GF16 adder wrapper for LUT measurement reproducibility.
// Instantiate gf_adder_param at GF16 parameters (E=6, M=9, HAS_INF=1).
// Usage: yosys -p "read_verilog gf_adder_param.v gf16_param_top.v; synth_xilinx -flatten -abc9 -nocarry -arch xc7; stat"
module gf16_param_top(
    input clk, input rst,
    input in_valid, input [15:0] in_a, input [15:0] in_b,
    output in_ready, output out_valid, output [15:0] out_y, input out_ready
);
    gf_adder_param #(.EXP_BITS(6), .MANT_BITS(9), .HAS_INF(1)) u (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_a(in_a), .in_b(in_b),
        .in_ready(in_ready), .out_valid(out_valid), .out_y(out_y), .out_ready(out_ready)
    );
endmodule
