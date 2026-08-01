`timescale 1ns / 1ps
//=============================================================================
// trinet_siphash24_tb — hold the RTL to the published SipHash-2-4 law.
//
// Reference values produced by Zig's std.hash.SipHash64(2,4), which reproduces
// the vectors from the SipHash paper. Two keys are used: a wrong key constant
// baked into the RTL would pass a single-key test.
//
// Author: Dmitrii Vasilev (@gHashTag)
//=============================================================================
module trinet_siphash24_tb;

    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg          rst = 1'b1;
    reg          start = 1'b0;
    reg  [207:0] msg;
    reg  [127:0] key;
    wire [63:0]  tag;
    wire         done;

    trinet_siphash24 #(.MSG_BYTES(26)) dut (
        .clk(clk), .rst(rst), .start(start), .msg(msg), .key(key),
        .tag(tag), .done(done));

    integer fails = 0;
    integer waited;

    task run_one(input [207:0] m, input [127:0] k, input [63:0] expected, input [127:0] label);
        begin
            msg = m; key = k;
            @(posedge clk); start = 1'b1;
            @(posedge clk); start = 1'b0;
            waited = 0;
            while (!done && waited < 200) begin
                @(posedge clk);
                waited = waited + 1;
            end
            if (!done) begin
                $display("  %0s: FAIL never completed", label);
                fails = fails + 1;
            end else if (tag !== expected) begin
                $display("  %0s: FAIL tag %016h != expected %016h", label, tag, expected);
                fails = fails + 1;
            end else begin
                $display("  %0s: ok  %016h  (%0d cycles)", label, tag, waited);
            end
            @(posedge clk);
        end
    endtask

    initial begin
        #40 rst = 1'b0;
        @(posedge clk);

        // msg = bytes 0x00..0x19, key = bytes 0x00..0x0f
        run_one(208'h191817161514131211100f0e0d0c0b0a09080706050403020100,
                128'h0f0e0d0c0b0a09080706050403020100,
                64'h17d835b85bbb15f3, "vector 1  ");

        // Same message, all-0xA5 key: proves the key actually reaches the state.
        run_one(208'h191817161514131211100f0e0d0c0b0a09080706050403020100,
                128'hA5A5A5A5A5A5A5A5A5A5A5A5A5A5A5A5,
                64'h8e94b97f19aef511, "vector 2  ");

        // Repeat vector 1 to confirm the FSM returns to a clean state.
        run_one(208'h191817161514131211100f0e0d0c0b0a09080706050403020100,
                128'h0f0e0d0c0b0a09080706050403020100,
                64'h17d835b85bbb15f3, "vector 1'");

        $display("");
        if (fails == 0) $display("TB PASS — the RTL reproduces SipHash-2-4");
        else            $display("TB FAIL — %0d checks failed", fails);
        $finish;
    end

    initial begin #500000; $display("TB FAIL: global timeout"); $finish; end

endmodule
