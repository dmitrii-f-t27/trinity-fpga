`timescale 1ns / 1ps
// tb_gf64_pipeline — verifies gf_adder_param PIPELINE=1 (2-stage) at GF64 (E=24, M=39).
//
// Two test surfaces:
//   (1) bit-exact parity with the same silicon-failure vectors as tb_gf64_inline.v
//       (functional correctness through the 2-stage datapath)
//   (2) latency check — out_valid asserts EXACTLY 2 posedges after the accept edge
//       (1 cycle for stage-1 latch + 1 cycle for stage-2 output register)
//
// Handshake: out_ready tied to 1 (matches the GF64 wrapper). The check task drives
// in_valid for a single cycle, then counts posedges until out_valid rises.
module tb_gf64_pipeline;
    reg clk = 0;
    reg rst = 1;
    reg in_valid = 0;
    reg [63:0] in_a, in_b;
    wire in_ready;
    wire out_valid;
    wire [63:0] out_y;
    reg out_ready = 1;

    gf_adder_param #(
        .EXP_BITS(24),
        .MANT_BITS(39),
        .HAS_INF(0),
        .PIPELINE(1)
    ) DUT (
        .clk(clk), .rst(rst),
        .in_valid(in_valid), .in_a(in_a), .in_b(in_b), .in_ready(in_ready),
        .out_valid(out_valid), .out_y(out_y), .out_ready(out_ready)
    );

    always #5 clk = ~clk;

    integer errors = 0, total = 0;
    integer latency_errors = 0;

    // Functional check + latency measurement.
    // All sampling at negedge (clean NBA timing — DUT outputs settle before read).
    // Pulse in_valid for exactly ONE cycle (assert at negedge, hold through one
    // posedge, deassert at next negedge). The posedge between the two negedges
    // is the accept edge where the DUT samples in_valid=1.
    //
    // Latency = number of negedge-to-negedge clk periods from in_valid assertion
    // to out_valid observation. PIPELINE=1 must give latency == 2
    // (1-cycle stage-1 latch + 1-cycle stage-2 output register). The original
    // combinational datapath (PIPELINE=0) gives latency == 1.
    task check;
        input [63:0] a;
        input [63:0] b;
        input [63:0] expected;
        integer cycles;
        begin
            // Sync to negedge first (avoids posedge races with the DUT).
            @(negedge clk);
            // Drain any previous output: wait for out_valid to fall.
            while (out_valid === 1'b1) @(negedge clk);
            // Confirm pipeline is ready to accept.
            while (in_ready !== 1'b1) @(negedge clk);

            // Assert in_valid with operands at negedge. DUT samples at next posedge.
            in_valid = 1; in_a = a; in_b = b;
            cycles = 0;
            // Walk forward one clk period at a time, sampling out_valid at negedge.
            // Hold in_valid high for exactly one posedge, then deassert at the
            // following negedge (clean — no posedge race with the DUT).
            while (out_valid !== 1'b1 && cycles < 10) begin
                @(posedge clk);
                @(negedge clk);
                if (cycles === 0) in_valid = 0;  // deassert after the accept edge
                cycles = cycles + 1;
            end

            total = total + 1;
            if (out_valid !== 1'b1) begin
                errors = errors + 1;
                $display("TIMEOUT: a=%h b=%h (no out_valid after %0d cycles)", a, b, cycles);
            end else if (out_y !== expected) begin
                errors = errors + 1;
                $display("MISMATCH: a=%h b=%h got=%h exp=%h", a, b, out_y, expected);
            end else begin
                $display("OK (latency=%0d): a=%h b=%h => %h", cycles, a, b, out_y);
            end

            // Latency assertion: PIPELINE=1 requires exactly 2 negedge-to-negedge
            // cycles from in_valid assertion to out_valid observation.
            if (out_valid === 1'b1 && cycles !== 2) begin
                latency_errors = latency_errors + 1;
                $display("  LATENCY FAIL: expected 2, got %0d", cycles);
            end
        end
    endtask

    initial begin
        repeat(4) @(posedge clk);
        rst = 0;
        repeat(3) @(posedge clk);

        // ---- Silicon-failure parity vectors (mirror of tb_gf64_inline.v) ----
        // -1.0 + 1.0 = +0
        check(64'hBFFFFF8000000000, 64'h3FFFFF8000000000, 64'h0000000000000000);
        // -2.0 + 0 = -2.0
        check(64'hC000000000000000, 64'h0000000000000000, 64'hC000000000000000);
        // +1.0 + 0 = +1.0
        check(64'h3FFFFF8000000000, 64'h0000000000000000, 64'h3FFFFF8000000000);
        // -0 + 0 = +0
        check(64'h8000000000000000, 64'h0000000000000000, 64'h0000000000000000);
        // +1.0 + +1.0 = +2.0
        check(64'h3FFFFF8000000000, 64'h3FFFFF8000000000, 64'h4000000000000000);
        // +1.0 + (-0.5) = +0.5
        check(64'h3FFFFF8000000000, 64'hBFFFFF0000000000, 64'h3FFFFF0000000000);
        // max-exp finite + 1.0 = max-exp (1.0 vanishes below ULP)
        check(64'h7FFFFF8000000000, 64'h3FFFFF8000000000, 64'h7FFFFF8000000000);
        // (+max) + (-max) = +0
        check(64'h7FFFFF8000000000, 64'hFFFFFF8000000000, 64'h0000000000000000);
        // 1.5 + 0.5 = 2.0
        check(64'h3FFFFFC000000000, 64'h3FFFFF0000000000, 64'h4000000000000000);

        $display("");
        $display("RESULT: gf64_pipeline %0d/%0d bit-exact (errors=%0d, latency_errors=%0d)",
                 total - errors, total, errors, latency_errors);
        if (errors == 0 && latency_errors == 0)
            $display("ALL_PASS");
        else
            $display("FAIL");
        $finish;
    end

    // Watchdog
    initial begin
        #100000;
        $display("FAIL: TIMEOUT");
        $finish;
    end
endmodule
