`timescale 1ns / 1ps
//=============================================================================
// trinet_setkey_tb — the key arrives over the wire, once.
//
// Four properties, and the last two are the ones worth having:
//
//   1. An unkeyed node computes the dot product and says STATUS=NO_KEY.
//   2. op 0x02 installs a key and the acknowledgement is tagged with the key
//      just installed, so the host can tell acceptance from an echo.
//   3. Afterwards, MAC jobs verify under that key. Golden tags come from the
//      independent Python implementation, never from this RTL.
//   4. A SECOND op 0x02 changes nothing. This is the property the whole design
//      rests on: if the key could be replaced at any time, anyone reaching the
//      wire could overwrite the operator's key and every later receipt would
//      verify under theirs.
//
// Author: Dmitrii Vasilev (@gHashTag)
//=============================================================================

module trinet_setkey_tb;

`ifndef TB_BAUD_DIV
  `define TB_BAUD_DIV 16
`endif
    localparam integer BAUD_DIV   = `TB_BAUD_DIV;
    localparam real    CLK_PERIOD = 14.4;
    localparam real    BIT_TIME   = BAUD_DIV * CLK_PERIOD;

    localparam [7:0] OP_MAC32  = 8'h01;
    localparam [7:0] OP_SETKEY = 8'h02;
    localparam [7:0] ST_OK = 8'h01, ST_KEY_SET = 8'h02,
                     ST_KEY_LOCKED = 8'h03, ST_NO_KEY = 8'h04;

    localparam [31:0] NODE = 32'h5452494E;

    // First key: bytes 00..0f on the wire. Second (rejected) key: ff..f0.
    // Both are test vectors and neither may ever deploy.
    localparam [127:0] KEY1_WIRE = 128'h000102030405060708090a0b0c0d0e0f;
    localparam [127:0] KEY2_WIRE = 128'hfffefdfcfbfaf9f8f7f6f5f4f3f2f1f0;

    reg  clk = 1'b0, rst = 1'b1, uart_rx = 1'b1;
    wire uart_tx, frame_seen, result_nonzero;
    always #(CLK_PERIOD/2.0) clk = ~clk;

    trinet_node_core #(.BAUD_DIV_P(BAUD_DIV), .RECEIPT_KEY(128'h0)) dut (
        .clk(clk), .rst(rst), .node_id(NODE), .uart_rx(uart_rx),
        .uart_tx(uart_tx), .frame_seen(frame_seen), .result_nonzero(result_nonzero));

    integer pass, fail;

    task uart_send_byte(input [7:0] b);
        integer bi;
        begin
            uart_rx = 1'b0; #(BIT_TIME);
            for (bi = 0; bi < 8; bi = bi + 1) begin uart_rx = b[bi]; #(BIT_TIME); end
            uart_rx = 1'b1; #(BIT_TIME);
        end
    endtask

    task uart_recv_byte(output [7:0] b, output reg timed_out);
        integer bi; real waited;
        begin
            b = 8'h00; timed_out = 1'b0; waited = 0.0;
            while (uart_tx === 1'b1 && waited < 400.0 * BIT_TIME) begin
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

    reg [7:0]  resp [0:18];
    reg        timed_out;
    reg [63:0] got_tag;
    reg [7:0]  got_status, got_y;
    integer    k;

    // Sends one request and fills resp[]. w_hi/x_hi are the 8-byte fields in
    // transmission order: byte 0 of the field is the MSB of the literal.
    task do_request(input [7:0] op, input [31:0] nonce,
                    input [63:0] wfield, input [63:0] xfield);
        begin
            uart_send_byte(8'hAA);
            uart_send_byte(8'h55);
            uart_send_byte(op);
            for (k = 0; k < 4; k = k + 1) uart_send_byte(nonce[8*(3-k) +: 8]);
            for (k = 0; k < 8; k = k + 1) uart_send_byte(wfield[8*(7-k) +: 8]);
            for (k = 0; k < 8; k = k + 1) uart_send_byte(xfield[8*(7-k) +: 8]);
            uart_send_byte(8'h00);

            for (k = 0; k < 19; k = k + 1) begin
                uart_recv_byte(resp[k], timed_out);
                if (timed_out) begin
                    $display("  FAIL timeout at response byte %0d", k);
                    fail = fail + 1; k = 19;
                end
            end
            got_y      = resp[1];
            got_status = resp[2];
            got_tag    = {resp[18], resp[17], resp[16], resp[15],
                          resp[14], resp[13], resp[12], resp[11]};
        end
    endtask

    task check_status(input [8*24:1] what, input [7:0] want);
        begin
            if (got_status === want) begin
                pass = pass + 1;
                $display("  ok   %0s status=%02x", what, got_status);
            end else begin
                fail = fail + 1;
                $display("  FAIL %0s status=%02x, wanted %02x", what, got_status, want);
            end
        end
    endtask

    task check_tag(input [8*24:1] what, input [63:0] want);
        begin
            if (got_tag === want) begin
                pass = pass + 1;
                $display("  ok   %0s tag=%016h", what, got_tag);
            end else begin
                fail = fail + 1;
                $display("  FAIL %0s tag=%016h, wanted %016h", what, got_tag, want);
            end
        end
    endtask

    // Golden tags, computed by conformance/trinet_mac32_conformance_ax7203.py
    // under KEY1 and node id 0x5452494E. Regenerate with tools/gen_setkey_golden
    // rather than by reading them off this RTL.
`include "trinet_setkey_golden.vh"

    initial begin
        pass = 0; fail = 0;
        rst = 1'b1; #(CLK_PERIOD * 20); rst = 1'b0; #(BIT_TIME * 6);

        $display("1. unkeyed node still computes, but will not sign");
        do_request(OP_MAC32, 32'h00000001, 64'h5555555555555555, 64'h5555555555555555);
        check_status("unkeyed mac", ST_NO_KEY);
        if (got_y !== 8'h20) begin
            fail = fail + 1; $display("  FAIL unkeyed y=%02x, wanted 20", got_y);
        end else begin
            pass = pass + 1; $display("  ok   unkeyed y=%02x (arithmetic works without a key)", got_y);
        end

        $display("2. the key arrives, and the ack is tagged with it");
        do_request(OP_SETKEY, 32'h00000002, KEY1_WIRE[127:64], KEY1_WIRE[63:0]);
        check_status("setkey", ST_KEY_SET);
        check_tag("setkey ack", GOLD_SETKEY_ACK);

        $display("3. work now verifies under the installed key");
        do_request(OP_MAC32, 32'h00000003, 64'h5555555555555555, 64'h5555555555555555);
        check_status("keyed mac", ST_OK);
        check_tag("keyed mac", GOLD_MAC_A);

        do_request(OP_MAC32, 32'h00000004, 64'h5555555555555555, 64'haaaaaaaaaaaaaaaa);
        check_status("keyed mac neg", ST_OK);
        check_tag("keyed mac neg", GOLD_MAC_B);

        $display("4. a second key is refused, and the first still signs");
        do_request(OP_SETKEY, 32'h00000005, KEY2_WIRE[127:64], KEY2_WIRE[63:0]);
        check_status("second setkey", ST_KEY_LOCKED);

        do_request(OP_MAC32, 32'h00000006, 64'h5555555555555555, 64'h5555555555555555);
        check_status("mac after refused setkey", ST_OK);
        check_tag("still the FIRST key", GOLD_MAC_C);

        $display("SIM RESULT: %0d passed, %0d failed", pass, fail);
        if (fail == 0) $display("TB PASS"); else $display("TB FAIL");
        $finish;
    end

    initial begin #(2_000_000_000); $display("TB FAIL: global timeout"); $finish; end

endmodule
