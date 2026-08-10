// Exhaustive stimulus for zeck_reenc16: every one of the 65,536 inputs.
//
// The published figure for this unit was "oracle-checked 40/40", and 40 vectors
// against a 2^16 input space is a spot check, not a proof. The space is small
// enough to sweep completely, so it is swept completely: this testbench emits
// one "x z" line per input and zeck_reenc16_oracle.py decides the verdict.
//
//   iverilog -g2005 -o /tmp/zeck16.vvp zeck_reenc16.v zeck_reenc16_tb.v
//   vvp /tmp/zeck16.vvp > /tmp/zeck16.txt
//   python3 zeck_reenc16_oracle.py /tmp/zeck16.txt
//
// The DUT registers its output, so each input is held for two edges and the
// result is sampled one cycle behind the drive -- reading z in the same cycle
// as x would compare an input against the previous input's answer, which is a
// mistake that still passes on long runs of equal outputs.
`default_nettype none
module zeck_reenc16_tb;
    reg         clk = 1'b0;
    reg  [15:0] x   = 16'd0;
    wire [22:0] z;
    integer     i;
    reg  [15:0] x_d;

    zeck_reenc16 dut (.clk(clk), .x(x), .z(z));

    always #5 clk = ~clk;

    initial begin
        // Prime the pipeline, then sweep. x_d carries the input that produced
        // the z being printed.
        @(negedge clk);
        for (i = 0; i < 65536; i = i + 1) begin
            x = i[15:0];
            @(posedge clk);
            x_d = x;
            @(negedge clk);
            $display("%0d %0d", x_d, z);
        end
        $finish;
    end
endmodule
