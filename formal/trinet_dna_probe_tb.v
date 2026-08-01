`timescale 1ns / 1ps
//=============================================================================
// trinet_dna_probe_tb — check the DNA read sequence and framing before
// spending a synthesis run and a 13-minute flash on it.
//
// The DNA_PORT stub below models the documented behaviour: READ high on a
// rising edge loads the value into a shift register and presents its top bit;
// SHIFT high walks the rest out, one bit per clock, most significant first.
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

module DNA_PORT #(
    parameter [56:0] SIM_DNA_VALUE = 57'h0
) (
    output wire DOUT,
    input  wire CLK, DIN, READ, SHIFT
);
    reg [56:0] sr = 57'h0;
    assign DOUT = sr[56];
    always @(posedge CLK) begin
        if (READ) sr <= SIM_DNA_VALUE;
        else if (SHIFT) sr <= {sr[55:0], DIN};
    end
endmodule


module trinet_dna_probe_tb;

    localparam integer BAUD_DIV   = 434;
    localparam real    CLK_PERIOD = 14.4;
    localparam real    BIT_TIME   = BAUD_DIV * CLK_PERIOD;
    localparam [56:0]  EXPECT_DNA = 57'h0AB_CDEF_1234_5678;

    reg  rst_n = 1'b0;
    reg  uart_rx = 1'b1;
    wire uart_tx;
    wire [3:0] led;

    trinet_dna_probe_ax7203 dut (.rst_n(rst_n), .uart_rx(uart_rx), .uart_tx(uart_tx), .led(led));

    task uart_send_byte(input [7:0] b);
        integer bi;
        begin
            uart_rx = 1'b0; #(BIT_TIME);
            for (bi = 0; bi < 8; bi = bi + 1) begin uart_rx = b[bi]; #(BIT_TIME); end
            uart_rx = 1'b1; #(BIT_TIME);
        end
    endtask

    task uart_recv_byte(output [7:0] b, output reg timed_out);
        integer bi;
        real waited;
        begin
            b = 8'h00; timed_out = 1'b0; waited = 0.0;
            while (uart_tx === 1'b1 && waited < 300.0 * BIT_TIME) begin
                #(BIT_TIME / 8.0); waited = waited + BIT_TIME / 8.0;
            end
            if (uart_tx !== 1'b0) timed_out = 1'b1;
            else begin
                #(BIT_TIME * 1.5);
                for (bi = 0; bi < 8; bi = bi + 1) begin b[bi] = uart_tx; #(BIT_TIME); end
                #(BIT_TIME * 0.5);
            end
        end
    endtask

    reg [7:0] resp [0:10];
    reg       timed_out;
    integer   k, round, fails;
    reg [63:0] got;

    task one_request;
        begin
            uart_send_byte(8'hAA);
            uart_send_byte(8'h55);
            uart_send_byte(8'h10);   // OP = read DNA
            uart_send_byte(8'h00);   // TRIG
            for (k = 0; k < 11; k = k + 1) begin
                uart_recv_byte(resp[k], timed_out);
                if (timed_out) begin
                    $display("  FAIL timeout on response byte %0d", k);
                    fails = fails + 1;
                    k = 11;
                end
            end
        end
    endtask

    initial begin
        fails = 0;
        rst_n = 1'b0; #1000; rst_n = 1'b1; #(BIT_TIME * 4);

        // Two rounds: the second exercises the cached path, and a device DNA
        // that changed between reads would mean the probe is reading noise.
        for (round = 0; round < 2; round = round + 1) begin
            one_request;
            got = {resp[9], resp[8], resp[7], resp[6], resp[5], resp[4], resp[3], resp[2]};
            $display("round %0d: status=%02x dna=%016h bits=%0d", round, resp[1], got, resp[10]);

            if (resp[0] !== 8'hA5)              begin $display("  FAIL magic"); fails = fails + 1; end
            if (resp[1] !== 8'h01)              begin $display("  FAIL status not ok"); fails = fails + 1; end
            if (resp[10] !== 8'd57)             begin $display("  FAIL bit count"); fails = fails + 1; end
            if (got[56:0] !== EXPECT_DNA)       begin
                $display("  FAIL dna %014h != expected %014h", got[56:0], EXPECT_DNA);
                fails = fails + 1;
            end
            if (got[63:57] !== 7'd0)            begin $display("  FAIL padding not zero"); fails = fails + 1; end
        end

        $display("");
        if (fails == 0) $display("TB PASS — the DNA read sequence and framing are correct");
        else            $display("TB FAIL — %0d checks failed", fails);
        $finish;
    end

    initial begin #(500_000_000); $display("TB FAIL: global timeout"); $finish; end

endmodule
