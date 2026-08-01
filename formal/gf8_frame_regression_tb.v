`timescale 1ns / 1ps
//=============================================================================
// gf8_frame_regression_tb — does the shipped conformance host still address
// the gf8 adder's operands?
//
// `fpga/vivado/gf8_clean_ax7203.v` parses six body bytes after the AA 55 magic:
//
//     AA 55 | op_a[7:0] op_a[15:8] op_b[7:0] op_b[15:8] | TRIG
//
// and feeds the core from `op_a[7:0]` and `op_b[7:0]`.
//
// `conformance/gf8_add_conformance_ax7203.py` builds its packet as
//
//     FRAME = bytes([0xAA, 0x55, 0x00])
//     pkt   = FRAME + bytes([a, 0, b, 0, 0x00])
//
// which puts an extra 0x00 between the magic and the operands. This testbench
// drives the DUT with both byte sequences and reports what the core actually
// receives, so the question is settled by the hardware description rather than
// by reading Python.
//
// Author: Dmitrii Vasilev (@gHashTag)
//=============================================================================

module STARTUPE2 #(
    parameter PROG_USR = "FALSE",
    parameter real SIM_CCLK_FREQ = 0.0
) (
    output wire CFGCLK,
    output reg  CFGMCLK,
    output reg  EOS,
    input  wire CLK, GSR, GTS, KEYCLEARB, PACK,
    input  wire USRCCLKO, USRCCLKTS, USRDONEO, USRDONETS
);
    assign CFGCLK = 1'b0;
    initial begin CFGMCLK = 1'b0; EOS = 1'b0; #200 EOS = 1'b1; end
    always #7.2 CFGMCLK = ~CFGMCLK;
endmodule


module gf8_frame_regression_tb;

    localparam integer BAUD_DIV   = 434;
    localparam real    CLK_PERIOD = 14.4;
    localparam real    BIT_TIME   = BAUD_DIV * CLK_PERIOD;

    reg  rst_n = 1'b0;
    reg  uart_rx = 1'b1;
    wire uart_tx;
    wire [3:0] led;

    gf8_clean_ax7203 dut (.rst_n(rst_n), .uart_rx(uart_rx), .uart_tx(uart_tx), .led(led));

    task uart_send_byte(input [7:0] b);
        integer bi;
        begin
            uart_rx = 1'b0; #(BIT_TIME);
            for (bi = 0; bi < 8; bi = bi + 1) begin uart_rx = b[bi]; #(BIT_TIME); end
            uart_rx = 1'b1; #(BIT_TIME);
        end
    endtask

    localparam [7:0] TEST_A = 8'h3C;   // some non-zero gf8 code
    localparam [7:0] TEST_B = 8'h41;

    integer fails;

    initial begin
        fails = 0;
        rst_n = 1'b0; #1000; rst_n = 1'b1; #(BIT_TIME * 4);

        // --- the frame the shipped host sends -------------------------------
        uart_send_byte(8'hAA);
        uart_send_byte(8'h55);
        uart_send_byte(8'h00);          // <- the byte under investigation
        uart_send_byte(TEST_A);
        uart_send_byte(8'h00);
        uart_send_byte(TEST_B);
        uart_send_byte(8'h00);
        uart_send_byte(8'h00);
        #(BIT_TIME * 4);

        $display("shipped host frame  AA 55 00 %02x 00 %02x 00 00", TEST_A, TEST_B);
        $display("  core received     a=%02x b=%02x", dut.add_a, dut.add_b);
        if (dut.add_a === TEST_A && dut.add_b === TEST_B) begin
            $display("  -> operands addressed correctly");
        end else begin
            $display("  -> OPERANDS LOST: the adder is being fed %02x + %02x", dut.add_a, dut.add_b);
            fails = fails + 1;
        end

        #(BIT_TIME * 8);

        // --- the frame the RTL actually parses -------------------------------
        uart_send_byte(8'hAA);
        uart_send_byte(8'h55);
        uart_send_byte(TEST_A);
        uart_send_byte(8'h00);
        uart_send_byte(TEST_B);
        uart_send_byte(8'h00);
        uart_send_byte(8'h00);
        #(BIT_TIME * 4);

        $display("corrected frame     AA 55 %02x 00 %02x 00 00", TEST_A, TEST_B);
        $display("  core received     a=%02x b=%02x", dut.add_a, dut.add_b);
        if (dut.add_a === TEST_A && dut.add_b === TEST_B) begin
            $display("  -> operands addressed correctly");
        end else begin
            $display("  -> still wrong: %02x + %02x", dut.add_a, dut.add_b);
            fails = fails + 1;
        end

        $display("");
        if (fails == 1)
            $display("VERDICT: the shipped frame loses the operands; removing the extra byte fixes it");
        else if (fails == 0)
            $display("VERDICT: both frames address the operands — no regression here");
        else
            $display("VERDICT: neither frame addresses the operands — investigate further");
        $finish;
    end

    initial begin #(500_000_000); $display("TB timeout"); $finish; end

endmodule
