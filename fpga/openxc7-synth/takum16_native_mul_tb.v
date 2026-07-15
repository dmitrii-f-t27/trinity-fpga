`timescale 1ns / 1ps
// takum16_native_mul_tb.v — verifies HW against the validated Python prototype.
// Reads (a,b,expected) hex triples from takum16_mul_vectors.txt.
module takum16_native_mul_tb;
    reg clk=0, rst=1;
    reg in_valid=0; reg [15:0] in_a, in_b;
    wire in_ready, out_valid; wire [15:0] out_y; reg out_ready=1;

    takum16_native_mul dut (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_a(in_a), .in_b(in_b),
        .in_ready(in_ready), .out_valid(out_valid), .out_y(out_y), .out_ready(out_ready)
    );

    always #5 clk = ~clk;

    integer fd, r, n=0, fail=0;
    reg [15:0] a,b,exp, last_a, last_b;
    reg [127:0] line;

    task automatic push;
        input [15:0] aa; input [15:0] bb;
        begin
            @(negedge clk);
            in_a = aa; in_b = bb; in_valid = 1'b1; last_a = aa; last_b = bb;
            @(negedge clk);
            // wait until accepted
            while (!in_ready) @(negedge clk);
            in_valid = 1'b0;
        end
    endtask

    task automatic pop_check;
        input [15:0] expected;
        begin
            // wait for a valid output
            while (!out_valid) @(negedge clk);
            if (out_y !== expected) begin
                fail = fail + 1;
                if (fail <= 40)
                    $display("FAIL: a=%h b=%h y=%h exp=%h", last_a, last_b, out_y, expected);
            end
            n = n + 1;
        end
    endtask

    initial begin
        fd = $fopen("takum16_mul_vectors.txt","r");
        if (fd == 0) begin $display("ERROR: cannot open vectors"); $finish; end
        repeat (3) @(negedge clk);
        rst = 0;
        repeat (2) @(negedge clk);

        // stream all vectors: drive one, drain one (DUT is 1-deep)
        r = $fscanf(fd, "%h %h %h\n", a, b, exp);
        while (r == 3) begin
            push(a, b);
            pop_check(exp);
            r = $fscanf(fd, "%h %h %h\n", a, b, exp);
        end
        $fclose(fd);

        $display("==================================================");
        if (fail == 0)
            $display("TAKUM16_NATIVE_MUL: PASS  (%0d vectors, 0 mismatches)", n);
        else
            $display("TAKUM16_NATIVE_MUL: FAIL  (%0d / %0d mismatches)", fail, n);
        $display("==================================================");
        $finish;
    end

    // safety timeout
    initial begin
        #2000000;
        $display("TIMEOUT");
        $finish;
    end
endmodule
