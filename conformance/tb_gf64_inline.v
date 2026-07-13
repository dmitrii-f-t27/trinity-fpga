`timescale 1ns / 1ps
// Minimal inline testbench — targets exact GF64 silicon failures
// Tests gf_adder_param at E=24, M=39, HAS_INF=1 (matching wrapper)
module tb_gf64_inline;
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
        .HAS_INF(1)
    ) DUT (
        .clk(clk), .rst(rst),
        .in_valid(in_valid), .in_a(in_a), .in_b(in_b), .in_ready(in_ready),
        .out_valid(out_valid), .out_y(out_y), .out_ready(out_ready)
    );

    always #5 clk = ~clk;

    integer errors = 0, total = 0;

    task check;
        input [63:0] a;
        input [63:0] b;
        input [63:0] expected;
        integer timeout;
        begin
            @(negedge clk);
            in_valid = 1; in_a = a; in_b = b;
            @(negedge clk);
            in_valid = 0;
            timeout = 0;
            while (!out_valid && timeout < 20) begin
                @(posedge clk);
                timeout = timeout + 1;
            end
            total = total + 1;
            if (out_y !== expected) begin
                errors = errors + 1;
                $display("MISMATCH: a=%h b=%h got=%h exp=%h", a, b, out_y, expected);
            end else begin
                $display("OK: a=%h b=%h => %h", a, b, out_y);
            end
        end
    endtask

    initial begin
        repeat(4) @(posedge clk);
        rst = 0;
        repeat(2) @(posedge clk);

        // ---- Silicon failures from 87/128 run ----
        // -1.0 + 1.0 should = 0 (was: 0xbfffff7fffffff00 on silicon)
        // GF64: sign=1, exp=BIAS=8388607=0x7FFFFF, mant=0
        // one_pos = 0x3FFFFF8000000000
        // one_neg = 0xBFFFFF8000000000
        check(64'hBFFFFF8000000000, 64'h3FFFFF8000000000, 64'h0000000000000000);

        // -2.0 + 0 should = -2.0 (identity, was: 0xbfffe00000000000 on silicon)
        // two_neg = 0xC000000000000000
        check(64'hC000000000000000, 64'h0000000000000000, 64'hC000000000000000);

        // +1.0 + 0 should = +1.0 (identity)
        check(64'h3FFFFF8000000000, 64'h0000000000000000, 64'h3FFFFF8000000000);

        // -0 + 0 should = +0 (was: 0x3fffe00000000000 on silicon)
        check(64'h8000000000000000, 64'h0000000000000000, 64'h0000000000000000);

        // +1.0 + +1.0 = +2.0
        check(64'h3FFFFF8000000000, 64'h3FFFFF8000000000, 64'h4000000000000000);

        // +1.0 + (-0.5) = +0.5
        // half = 0x3FFFFF0000000000
        check(64'h3FFFFF8000000000, 64'hBFFFFF0000000000, 64'h3FFFFF0000000000);

        // ---- Inf/NaN (HAS_INF=1) ----
        // pos_inf = exp=0xFFFFFF, mant=0 = 0x7FFFFF8000000000... wait
        // exp_max = 2^24-1 = 16777215 = 0xFFFFFF
        // pos_inf = (0xFFFFFF << 39) = 0x7FFFFF8000000000
        // Wait: bit layout is [S:1][E:24][M:39]
        // pos_inf = 0 | (0xFFFFFF << 39) | 0
        // 0xFFFFFF << 39 = 0xFFFFFF * 2^39
        // 2^39 = 0x8000000000
        // 0xFFFFFF * 0x8000000000 = ?
        // 0xFFFFFF = 16777215
        // 16777215 * 549755813888 = 9223372036854775808 - 549755813888 = 9223371487098961920
        // = 0x7FFFFF8000000000
        // Inf + 1.0 = Inf
        check(64'h7FFFFF8000000000, 64'h3FFFFF8000000000, 64'h7FFFFF8000000000);
        // Inf + (-Inf) = NaN (canonical qNaN: exp=all-ones, mant=1)
        // qNaN = 0x7FFFFF8000000001
        check(64'h7FFFFF8000000000, 64'hFFFFFFFF80000000, 64'h7FFFFF8000000001);

        // ---- Normal arithmetic ----
        // 1.5 + 0.5 = 2.0
        // 1.5 = exp=BIAS, mant=0x8000000000 >> mant_bits... 
        // mant for 1.5: mant = 0.5 * 2^39 = 0x4000000000
        // 1.5 = 0x3FFFFF8000000000 | 0x4000000000 = 0x3FFFFFC000000000
        check(64'h3FFFFFC000000000, 64'h3FFFFF0000000000, 64'h4000000000000000);

        $display("");
        $display("RESULT: gf64_inline %0d/%0d bit-exact (errors=%0d)", total - errors, total, errors);
        if (errors == 0)
            $display("ALL_PASS");
        else
            $display("FAIL");
        $finish;
    end
endmodule
