`timescale 1ns / 1ps
// Testbench for gf_adder_param at gf64 (E=24, M=39, HAS_INF=1)
// Matches the silicon wrapper: corona_compute_gf64_add_ax7203.v uses HAS_INF(1)
module tb_gf_adder_gf64;
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

    integer fd, errors = 0, total = 0;
    reg [63:0] a, b, expected;
    reg [255:0] line;
    integer r;
    integer timeout;

    initial begin
        fd = $fopen("conformance/verify_adder_gf64_vectors.txt", "r");
        if (fd == 0) begin
            $display("ERROR: Cannot open vector file");
            $finish;
        end

        // Reset
        repeat(4) @(posedge clk);
        rst = 0;
        repeat(2) @(posedge clk);

        // Skip 3 header lines
        r = $fgets(line, fd);
        r = $fgets(line, fd);
        r = $fgets(line, fd);

        while (!$feof(fd)) begin
            r = $fscanf(fd, "%h %h %h\n", a, b, expected);
            if (r != 3) continue;

            // Drive input
            @(negedge clk);
            in_valid = 1; in_a = a; in_b = b;
            @(negedge clk);
            in_valid = 0;

            // Wait for output with timeout (max 10 cycles)
            timeout = 0;
            while (!out_valid && timeout < 20) begin
                @(posedge clk);
                timeout = timeout + 1;
            end

            total = total + 1;
            if (out_y !== expected) begin
                errors = errors + 1;
                if (errors <= 10)
                    $display("MISMATCH: a=%h b=%h got=%h exp=%h", a, b, out_y, expected);
            end
        end

        $display("RESULT: gf64 %0d/%0d bit-exact (errors=%0d)", total - errors, total, errors);
        $fclose(fd);
        if (errors == 0)
            $display("ALL_PASS");
        else
            $display("FAIL");
        $finish;
    end
endmodule
