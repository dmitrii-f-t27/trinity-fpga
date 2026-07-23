// tb_gf_decode_param_pipe.v -- self-checking iverilog witness for the 2-stage
// pipelined gf{N} decoder. Reads "GFHEX FP32HEX" vectors. For each vector it
// applies gf_in, waits LAT_FLUSH clocks for the pipeline to fully propagate,
// then samples fp32_out. This one-at-a-time settle avoids any streaming/
// latency-alignment ambiguity in the checker (the RTL is still a real 2-stage
// pipeline; we simply hold each input until its result emerges).
//
// Compile-time overrides: -DN=.. -DE=.. -DM=.. -DBIAS=.. -DVEC="file" -DNVEC=..
// Trinity Catalog-100 horizon-B routing prep, 2026-07-24.
`timescale 1ns/1ps
`ifndef N
  `define N 24
`endif
`ifndef E
  `define E 9
`endif
`ifndef M
  `define M 14
`endif
`ifndef BIAS
  `define BIAS 255
`endif
`ifndef VEC
  `define VEC "vec_gf24.txt"
`endif
`ifndef NVEC
  `define NVEC 30000
`endif

module tb;
    localparam integer N = `N, E = `E, M = `M, BIAS = `BIAS;
    localparam integer NV = `NVEC;
    localparam integer LAT_FLUSH = 4; // >= pipeline latency, margin included

    reg clk = 0, rst_n = 0;
    reg  [N-1:0] gf_in;
    wire [31:0]  fp32_out;
    wire is_nan_o, is_inf_o, is_zero_o, is_subnormal_o;

    gf_decode_param_pipe #(.N(N), .E(E), .M(M), .BIAS(BIAS)) dut (
        .clk(clk), .rst_n(rst_n), .gf_in(gf_in),
        .fp32_out(fp32_out), .is_nan_o(is_nan_o), .is_inf_o(is_inf_o),
        .is_zero_o(is_zero_o), .is_subnormal_o(is_subnormal_o));

    always #5 clk = ~clk;

    reg [N-1:0]  vin  [0:NV-1];
    reg [31:0]   vexp [0:NV-1];
    integer nread = 0;
    integer fd, r, i, j;
    integer fails = 0, checked = 0;

    function is_nan32; input [31:0] x;
        is_nan32 = (x[30:23] == 8'hFF) && (x[22:0] != 0);
    endfunction

    initial begin
        fd = $fopen(`VEC, "r");
        if (fd == 0) begin $display("ERROR: cannot open %s", `VEC); $finish; end
        while (!$feof(fd) && nread < NV) begin
            r = $fscanf(fd, "%h %h\n", vin[nread], vexp[nread]);
            if (r == 2) nread = nread + 1;
        end
        $fclose(fd);
        $display("loaded %0d vectors from %s (N=%0d E=%0d M=%0d BIAS=%0d)",
                 nread, `VEC, N, E, M, BIAS);

        rst_n = 0; gf_in = 0;
        @(posedge clk); @(posedge clk);
        rst_n = 1;

        for (i = 0; i < nread; i = i + 1) begin
            gf_in = vin[i];
            for (j = 0; j < LAT_FLUSH; j = j + 1) @(posedge clk);
            #1;
            if (is_nan32(vexp[i])) begin
                if (!is_nan32(fp32_out)) begin
                    fails = fails + 1;
                    if (fails <= 8) $display("FAIL idx=%0d gf=%h exp=NaN got=%h", i, vin[i], fp32_out);
                end
            end else if (fp32_out !== vexp[i]) begin
                fails = fails + 1;
                if (fails <= 8) $display("FAIL idx=%0d gf=%h exp=%h got=%h", i, vin[i], vexp[i], fp32_out);
            end
            checked = checked + 1;
        end

        $display("WITNESS RESULT: %0d/%0d bit-exact (fails=%0d)", checked - fails, checked, fails);
        if (fails != 0) $finish(1);
        $finish(0);
    end
endmodule
