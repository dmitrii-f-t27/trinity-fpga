`timescale 1ns / 1ps
//=============================================================================
// trinet_node_v2_tb — the keyed receipt, end to end over the real UART frame.
//
// Golden values from conformance/trinet_mac32_conformance_ax7203.py using its
// siphash24, under the DNA-derived node id the DNA_PORT stub yields
// (SIM_DNA_VALUE low 32 bits = 0x12345678) and the default receipt key.
//
// Author: Dmitrii Vasilev (@gHashTag)
//=============================================================================

module STARTUPE2 #(
    parameter PROG_USR = "FALSE",
    parameter real SIM_CCLK_FREQ = 0.0
) (
    output wire CFGCLK, output reg CFGMCLK, output reg EOS,
    input wire CLK, GSR, GTS, KEYCLEARB, PACK,
    input wire USRCCLKO, USRCCLKTS, USRDONEO, USRDONETS
);
    assign CFGCLK = 1'b0;
    initial begin CFGMCLK = 1'b0; EOS = 1'b0; #200 EOS = 1'b1; end
    always #7.2 CFGMCLK = ~CFGMCLK;
endmodule

module DNA_PORT #(parameter [56:0] SIM_DNA_VALUE = 57'h0) (
    output wire DOUT, input wire CLK, DIN, READ, SHIFT
);
    reg [56:0] sr = 57'h0;
    assign DOUT = sr[56];
    always @(posedge CLK) begin
        if (READ) sr <= SIM_DNA_VALUE;
        else if (SHIFT) sr <= {sr[55:0], DIN};
    end
endmodule


module trinet_node_v2_tb;

`ifndef TB_BAUD_DIV
  `define TB_BAUD_DIV 434
`endif
    localparam integer BAUD_DIV   = `TB_BAUD_DIV;
    localparam real    CLK_PERIOD = 14.4;
    localparam real    BIT_TIME   = BAUD_DIV * CLK_PERIOD;
    localparam [31:0]  EXPECT_ID  = 32'h12345678;   // low 32 bits of SIM_DNA_VALUE

    reg  rst_n = 1'b0;
    reg  uart_rx = 1'b1;
    wire uart_tx;
    wire [3:0] led;

    trinet_node_v2_ax7203 #(.USE_DNA(1), .BAUD_DIV_P(BAUD_DIV)) dut (
        .rst_n(rst_n), .uart_rx(uart_rx), .uart_tx(uart_tx), .led(led));

    localparam integer NVEC = 6;
    reg [31:0] v_nonce [0:NVEC-1];
    reg [63:0] v_w     [0:NVEC-1];
    reg [63:0] v_x     [0:NVEC-1];
    reg [7:0]  v_y     [0:NVEC-1];
    reg [63:0] v_tag   [0:NVEC-1];

    initial begin
        v_nonce[0]=32'h00000000; v_w[0]=64'h0000000000000000; v_x[0]=64'h0000000000000000; v_y[0]=8'h00; v_tag[0]=64'h5eae10b9c3869114;
        v_nonce[1]=32'h01000000; v_w[1]=64'h5555555555555555; v_x[1]=64'h5555555555555555; v_y[1]=8'h20; v_tag[1]=64'ha4ad572e33cc0ca6;
        v_nonce[2]=32'h02000000; v_w[2]=64'haaaaaaaaaaaaaaaa; v_x[2]=64'haaaaaaaaaaaaaaaa; v_y[2]=8'h20; v_tag[2]=64'hf022048fc96879f8;
        v_nonce[3]=32'h03000000; v_w[3]=64'h5555555555555555; v_x[3]=64'haaaaaaaaaaaaaaaa; v_y[3]=8'he0; v_tag[3]=64'ha5491c2feda487c3;
        v_nonce[4]=32'h04000000; v_w[4]=64'h0000000000000000; v_x[4]=64'h5555555555555555; v_y[4]=8'h00; v_tag[4]=64'he5babc78881f17c6;
        v_nonce[5]=32'h05000000; v_w[5]=64'h9999999999999999; v_x[5]=64'h9999999999999999; v_y[5]=8'h20; v_tag[5]=64'h62b7ea10a786f5f3;
    end

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

    reg [7:0] resp [0:18];
    reg       timed_out;
    integer   i, k, pass, fail;
    reg [31:0] got_id;
    reg [63:0] got_tag;
    reg ok;

    task run_job(input integer idx);
        begin
            ok = 1'b1;
            uart_send_byte(8'hAA);
            uart_send_byte(8'h55);
            uart_send_byte(8'h01);
            // Hex fields are stored in transmission order, so the first pair
            // sits in the high bytes — send them (N-1-k).
            for (k = 0; k < 4; k = k + 1) uart_send_byte(v_nonce[idx][8*(3-k) +: 8]);
            for (k = 0; k < 8; k = k + 1) uart_send_byte(v_w[idx][8*(7-k) +: 8]);
            for (k = 0; k < 8; k = k + 1) uart_send_byte(v_x[idx][8*(7-k) +: 8]);
            uart_send_byte(8'h00);

            for (k = 0; k < 19; k = k + 1) begin
                uart_recv_byte(resp[k], timed_out);
                if (timed_out) begin
                    $display("  [%0d] FAIL timeout at response byte %0d", idx, k);
                    ok = 1'b0; k = 19;
                end
            end
            if (!ok) begin fail = fail + 1; disable run_job; end

            got_id  = {resp[10], resp[9], resp[8], resp[7]};
            got_tag = {resp[18], resp[17], resp[16], resp[15],
                       resp[14], resp[13], resp[12], resp[11]};

            if (resp[0] !== 8'hA5)      begin $display("  [%0d] FAIL magic", idx); ok = 0; end
            if (resp[2] !== 8'h01)      begin $display("  [%0d] FAIL status", idx); ok = 0; end
            if (resp[1] !== v_y[idx])   begin $display("  [%0d] FAIL y %02x != %02x", idx, resp[1], v_y[idx]); ok = 0; end
            if (got_id !== EXPECT_ID)   begin $display("  [%0d] FAIL node id %08x != %08x (DNA not reaching the receipt)", idx, got_id, EXPECT_ID); ok = 0; end
            if (got_tag !== v_tag[idx]) begin $display("  [%0d] FAIL tag %016h != %016h", idx, got_tag, v_tag[idx]); ok = 0; end

            if (ok) pass = pass + 1; else fail = fail + 1;
        end
    endtask

    initial begin
        pass = 0; fail = 0;
        rst_n = 1'b0; #1000; rst_n = 1'b1; #(BIT_TIME * 6);
        for (i = 0; i < NVEC; i = i + 1) run_job(i);
        $display("SIM RESULT: %0d/%0d keyed receipts bit-exact (fails=%0d)", pass, NVEC, fail);
        if (fail == 0 && pass == NVEC) $display("TB PASS");
        else                           $display("TB FAIL");
        $finish;
    end

    initial begin #(2_000_000_000); $display("TB FAIL: global timeout"); $finish; end

endmodule
