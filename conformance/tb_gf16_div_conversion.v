`timescale 1ns / 1ps
// tb_gf16_div_conversion — simulate the two conversion stages of the gf16 DIV wrapper.
//
// Passes 101 and 105 repaired the stage that decodes a gf16 operand into binary32 and
// the stage that packs a binary32 quotient back into gf16. Neither repair had a test:
// the whole point of this campaign's last several passes is that untested code fails
// quietly, so repairing it and walking away would repeat the mistake being reported.
//
// The divider itself is not exercised. Its operands are forced, its result is forced,
// and only the wrapper's conversion is observed -- which is precisely the code that
// was changed, and nothing else.
//
//   iverilog -g2012 -o /tmp/tb tb_gf16_div_conversion.v \
//       ../fpga/openxc7-synth/corona_compute_gf16_div_ax7203.v \
//       ../fpga/openxc7-synth/gf_div_param.v
//   vvp /tmp/tb < vectors.txt
//
// stdin: one "A B" pair of hex words per line --
//   A = 16-bit gf16 operand to decode, B = 32-bit binary32 quotient to pack.
// stdout: "IN <fp32_a>" and "OUT <q_result>" per line, for the host to compare.

// STARTUPE2 is a Xilinx primitive with no simulation model here. The wrapper only
// takes CFGMCLK and EOS from it, so a free-running clock and a tied-high EOS are a
// faithful stand-in for what this testbench observes.
module STARTUPE2 #(parameter PROG_USR = "FALSE", parameter SIM_CCLK_FREQ = 0.0)
    (output CFGCLK, output reg CFGMCLK, output EOS,
     input CLK, input GSR, input GTS, input KEYCLEARB, input PACK,
     input USRCCLKO, input USRCCLKTS, input USRDONEO, input USRDONETS);
    assign CFGCLK = 1'b0;
    assign EOS = 1'b1;
    initial CFGMCLK = 1'b0;
    always #5 CFGMCLK = ~CFGMCLK;
endmodule

module tb_gf16_div_conversion;
    reg rst_n = 1'b0;
    wire uart_tx;
    wire [3:0] led;

    corona_compute_gf16_div_ax7203 dut (
        .rst_n(rst_n), .uart_rx(1'b1), .uart_tx(uart_tx), .led(led));

    integer n, code;
    reg [15:0] a_in;
    reg [31:0] q_in;

    initial begin
        #40 rst_n = 1'b1;
        #40;
        n = 0;
        while (1) begin
            code = $fscanf('h8000_0000, "%h %h\n", a_in, q_in);
            if (code != 2) begin
                $display("DONE %0d", n);
                $finish;
            end
            // stage 1: decode a gf16 operand into the binary32 the divider sees
            force dut.a_reg = a_in;
            // stage 2: pack a binary32 quotient back into gf16
            force dut.comp_result = q_in;
            #1;
            $display("IN %04h %08h OUT %08h %04h",
                     a_in, dut.fp32_a, q_in, dut.q_result);
            n = n + 1;
        end
    end
endmodule
