`timescale 1ns / 1ps
//=============================================================================
// trinet_mac32_tb — iverilog testbench for trinet_mac32_ax7203.
//
// Drives real UART frames into the DUT at the synthesised baud divisor and
// checks both the ternary dot product and the CRC-32 receipt tag against
// golden vectors produced by
//
//   python3 conformance/trinet_mac32_conformance_ax7203.py \
//       --emit-vectors /tmp/trinet_vec.txt --n 64
//
// Vector line format: NONCE(8 hex) W(16 hex) X(16 hex) Y(2 hex) CRC(8 hex)
//
// The point of simulating the full UART path, rather than the datapath alone,
// is that every RTL bug this project has caught on silicon lived in the frame
// path, not the arithmetic.
//
// Author: Dmitrii Vasilev (@gHashTag)
//=============================================================================

// Simulation stub for the Xilinx configuration-clock primitive.
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
    initial begin
        CFGMCLK = 1'b0;
        EOS = 1'b0;
        #200 EOS = 1'b1;
    end
    // ~69 MHz -> 14.4 ns period
    always #7.2 CFGMCLK = ~CFGMCLK;
endmodule


module trinet_mac32_tb;

    localparam integer BAUD_DIV   = 434;
    localparam real    CLK_PERIOD = 14.4;                    // ns, matches the stub
    localparam real    BIT_TIME   = BAUD_DIV * CLK_PERIOD;   // ns per UART bit
    localparam [31:0]  NODE_ID    = 32'h5452494E;            // "TRIN"

    localparam integer MAX_VEC = 512;

    reg  rst_n = 1'b0;
    reg  uart_rx = 1'b1;
    wire uart_tx;
    wire [3:0] led;

    trinet_mac32_ax7203 #(.NODE_ID(NODE_ID)) dut (
        .rst_n(rst_n), .uart_rx(uart_rx), .uart_tx(uart_tx), .led(led));

    //-------------------------------------------------------------------------
    // Golden vectors
    //-------------------------------------------------------------------------
    reg [31:0] v_nonce [0:MAX_VEC-1];
    reg [63:0] v_w     [0:MAX_VEC-1];
    reg [63:0] v_x     [0:MAX_VEC-1];
    reg [7:0]  v_y     [0:MAX_VEC-1];
    reg [31:0] v_crc   [0:MAX_VEC-1];

    integer n_vec;
    integer fh, code;
    reg [31:0] t_nonce, t_crc;
    reg [63:0] t_w, t_x;
    reg [7:0]  t_y;

    //-------------------------------------------------------------------------
    // UART helpers
    //-------------------------------------------------------------------------
    task uart_send_byte(input [7:0] b);
        integer bi;
        begin
            uart_rx = 1'b0;                       // start
            #(BIT_TIME);
            for (bi = 0; bi < 8; bi = bi + 1) begin
                uart_rx = b[bi];                  // LSB first
                #(BIT_TIME);
            end
            uart_rx = 1'b1;                       // stop
            #(BIT_TIME);
        end
    endtask

    task uart_recv_byte(output [7:0] b, output reg timed_out);
        integer bi;
        real    waited;
        begin
            b = 8'h00;
            timed_out = 1'b0;
            waited = 0.0;
            while (uart_tx === 1'b1 && waited < 200.0 * BIT_TIME) begin
                #(BIT_TIME / 8.0);
                waited = waited + BIT_TIME / 8.0;
            end
            if (uart_tx !== 1'b0) begin
                timed_out = 1'b1;
            end else begin
                #(BIT_TIME * 1.5);                // centre of bit 0
                for (bi = 0; bi < 8; bi = bi + 1) begin
                    b[bi] = uart_tx;
                    #(BIT_TIME);
                end
                // we are now inside the stop bit; wait it out
                #(BIT_TIME * 0.5);
            end
        end
    endtask

    //-------------------------------------------------------------------------
    // Job driver
    //-------------------------------------------------------------------------
    reg [7:0] resp [0:14];
    reg       rx_timeout;
    integer   i, k;
    integer   pass_count, fail_count;
    reg [7:0] got_y;
    reg [31:0] got_nonce, got_node, got_crc;
    reg       job_ok;

    task run_job(input integer idx);
        begin
            job_ok = 1'b1;

            // The vector file stores each field as hex in TRANSMISSION order,
            // so the first hex pair is the first byte on the wire. $fscanf %h
            // packs that into the HIGH bytes, hence the (N-1-k) indexing.
            uart_send_byte(8'hAA);
            uart_send_byte(8'h55);
            uart_send_byte(8'h01);                       // OP = MAC32
            for (k = 0; k < 4; k = k + 1)
                uart_send_byte(v_nonce[idx][8*(3-k) +: 8]);
            for (k = 0; k < 8; k = k + 1)
                uart_send_byte(v_w[idx][8*(7-k) +: 8]);
            for (k = 0; k < 8; k = k + 1)
                uart_send_byte(v_x[idx][8*(7-k) +: 8]);
            uart_send_byte(8'h00);                       // TRIG

            for (k = 0; k < 15; k = k + 1) begin
                uart_recv_byte(resp[k], rx_timeout);
                if (rx_timeout) begin
                    $display("  [%0d] FAIL timeout waiting for response byte %0d", idx, k);
                    job_ok = 1'b0;
                    k = 15;
                end
            end
            if (!job_ok) disable run_job;

            got_y = resp[1];
            // nonce is compared in wire order (first byte in the high slot) to
            // match how the vector file was read; node id and crc are compared
            // as little-endian scalars, which is how the RTL emits them.
            got_nonce = {resp[3], resp[4], resp[5], resp[6]};
            got_node  = {resp[10], resp[9], resp[8], resp[7]};
            got_crc   = {resp[14], resp[13], resp[12], resp[11]};

            if (resp[0] !== 8'hA5) begin
                $display("  [%0d] FAIL magic %02x != A5", idx, resp[0]); job_ok = 1'b0;
            end
            if (resp[2] !== 8'h01) begin
                $display("  [%0d] FAIL status %02x != 01", idx, resp[2]); job_ok = 1'b0;
            end
            if (got_y !== v_y[idx]) begin
                $display("  [%0d] FAIL y %02x != golden %02x", idx, got_y, v_y[idx]);
                job_ok = 1'b0;
            end
            if (got_nonce !== v_nonce[idx]) begin
                $display("  [%0d] FAIL nonce %08x != %08x", idx, got_nonce, v_nonce[idx]);
                job_ok = 1'b0;
            end
            if (got_node !== NODE_ID) begin
                $display("  [%0d] FAIL node %08x != %08x", idx, got_node, NODE_ID);
                job_ok = 1'b0;
            end
            if (got_crc !== v_crc[idx]) begin
                $display("  [%0d] FAIL crc %08x != golden %08x", idx, got_crc, v_crc[idx]);
                job_ok = 1'b0;
            end

            if (job_ok) pass_count = pass_count + 1;
            else        fail_count = fail_count + 1;
        end
    endtask

    //-------------------------------------------------------------------------
    // Main
    //-------------------------------------------------------------------------
    initial begin
        pass_count = 0;
        fail_count = 0;
        n_vec = 0;

        fh = $fopen("/tmp/trinet_vec.txt", "r");
        if (fh == 0) begin
            $display("ERROR: cannot open /tmp/trinet_vec.txt");
            $display("Run: python3 conformance/trinet_mac32_conformance_ax7203.py --emit-vectors /tmp/trinet_vec.txt --n 64");
            $finish;
        end
        while (n_vec < MAX_VEC) begin
            code = $fscanf(fh, "%h %h %h %h %h\n", t_nonce, t_w, t_x, t_y, t_crc);
            if (code != 5) n_vec = MAX_VEC;      // stop on EOF / malformed
            else begin
                v_nonce[n_vec] = t_nonce;
                v_w[n_vec]     = t_w;
                v_x[n_vec]     = t_x;
                v_y[n_vec]     = t_y;
                v_crc[n_vec]   = t_crc;
                n_vec = n_vec + 1;
            end
        end
        $fclose(fh);
        // n_vec was clobbered to MAX_VEC by the stop condition; recount properly
        while (n_vec > 0 && v_nonce[n_vec-1] === 32'hxxxxxxxx) n_vec = n_vec - 1;

        $display("trinet_mac32_tb: %0d golden vectors loaded", n_vec);

        rst_n = 1'b0;
        #1000;
        rst_n = 1'b1;
        #(BIT_TIME * 4);

        for (i = 0; i < n_vec; i = i + 1) run_job(i);

        $display("SIM RESULT: %0d/%0d jobs bit-exact (fails=%0d)",
                 pass_count, n_vec, fail_count);
        if (fail_count == 0 && pass_count > 0) $display("TB PASS");
        else                                   $display("TB FAIL");
        $finish;
    end

    initial begin
        #(2_000_000_000);
        $display("TB FAIL: global timeout");
        $finish;
    end

endmodule
