// tb_gf128_decode_fp64.v -- iverilog testbench, reads gf128_vectors.hex
// (produced by conformance/gf128_bitexact_oracle.py: "<128-bit raw> <64-bit expected>").
// Compares the RTL decode (witness C) against the python oracle bit-for-bit;
// NaN compared by class.
`timescale 1ns/1ps
module tb_gf128_decode_fp64;
    reg  [127:0] gf_in;
    wire [63:0]  fp64_out;
    gf128_decode_fp64 dut(.gf_in(gf_in), .fp64_out(fp64_out));

    integer fd, r, cnt, fails;
    reg [127:0] raw;
    reg [63:0]  exp;
    reg        dut_nan, exp_nan;

    initial begin
        cnt = 0; fails = 0;
        fd = $fopen("gf128_vectors.hex", "r");
        if (fd == 0) begin $display("ERROR: cannot open gf128_vectors.hex"); $finish; end
        while (!$feof(fd)) begin
            r = $fscanf(fd, "%h %h\n", raw, exp);
            if (r == 2) begin
                gf_in = raw;
                #1;
                dut_nan = (fp64_out[62:52] == 11'h7FF) && (fp64_out[51:0] != 52'd0);
                exp_nan = (exp[62:52]      == 11'h7FF) && (exp[51:0]      != 52'd0);
                if (fp64_out === exp || (dut_nan && exp_nan)) begin
                    cnt = cnt + 1;
                end else begin
                    fails = fails + 1;
                    if (fails <= 20)
                        $display("  MISMATCH raw=%032h dut=%016h exp=%016h", raw, fp64_out, exp);
                    cnt = cnt + 1;
                end
            end
        end
        $fclose(fd);
        $display("HW RESULT: %0d/%0d bit-exact (fails=%0d)", cnt-fails, cnt, fails);
        $finish;
    end
endmodule
