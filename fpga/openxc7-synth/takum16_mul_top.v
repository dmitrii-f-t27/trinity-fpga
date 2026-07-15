// takum16_mul_top.v — synthesis wrapper for LUT measurement reproducibility.
// Instantiates the native logarithmic takum16 multiplier.
// Usage:
//   yosys -p "read_verilog takum16_native_mul.v takum16_mul_top.v; \
//             synth_xilinx -flatten -abc9 -nocarry -arch xc7; stat"
module takum16_mul_top(
    input clk, input rst,
    input in_valid, input [15:0] in_a, input [15:0] in_b,
    output in_ready, output out_valid, output [15:0] out_y, input out_ready
);
    takum16_native_mul u (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_a(in_a), .in_b(in_b),
        .in_ready(in_ready), .out_valid(out_valid), .out_y(out_y), .out_ready(out_ready)
    );
endmodule
