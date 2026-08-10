// Directed + random stimulus for zeck_reenc32. This is a SAMPLE, not a sweep.
//
// zeck_reenc16 was checked exhaustively -- all 65,536 inputs -- because 2^16 is
// small. 2^32 is 4,294,967,296 inputs and cannot be swept here, so nothing this
// testbench produces may be called exhaustive. What it produces is a directed
// set aimed at the places a greedy renormaliser breaks, plus a fixed-seed
// random tail so the sample is not only the cases the author thought of.
//
// Directed set (all of it derived from the definition, not from the design):
//   (a) 0 and 1
//   (b) every Fibonacci number below 2^32, and each of them minus one and
//       plus one -- F(k)-1 is the classic worst case, since its Zeckendorf
//       word is the alternating 1010...1 pattern
//   (c) alternating-Fibonacci partial sums, built from the bottom and from the
//       top, with their neighbours -- the densest words, which keep the greedy
//       remainder alive through the longest run of compare-subtract stages
//   (d) the maximum, 2^32-1, and its neighbourhood
//
// Random tail: xorshift32 seeded with SEED = 32'h5EED1234, stated here and
// fixed forever. The PRNG is written out in full rather than calling $random so
// the same vectors come back on any simulator, not just this one.
//
//   iverilog -g2005 -o /tmp/zeck32.vvp zeck_reenc32.v zeck_reenc32_tb.v
//   vvp /tmp/zeck32.vvp > /tmp/zeck32.txt
//   python3 zeck_reenc32_oracle.py /tmp/zeck32.txt
//
// The DUT registers its output, so each input is held for two edges and the
// result is sampled one cycle behind the drive -- reading z in the same cycle
// as x would compare an input against the previous input's answer, which is a
// mistake that still passes on long runs of equal outputs.
`default_nettype none
module zeck_reenc32_tb;
    localparam integer NDIR_MAX = 512;          // slots for the directed set
    localparam integer NRAND    = 200000;       // random vectors
    localparam [31:0]  SEED     = 32'h5EED1234; // fixed, stated, never changed
    localparam [32:0]  MAXV     = 33'd4294967295;

    reg         clk = 1'b0;
    reg  [31:0] x   = 32'd0;
    wire [45:0] z;
    reg  [31:0] x_d;

    reg  [31:0] fib [0:45];
    reg  [31:0] vec [0:NDIR_MAX-1];
    integer     ndir;
    integer     i, j;
    reg  [32:0] acc;
    reg  [31:0] rnd;

    zeck_reenc32 dut (.clk(clk), .x(x), .z(z));

    always #5 clk = ~clk;

    // Append one directed vector, dropping anything outside the input range.
    task push(input [32:0] v);
        begin
            if (v <= MAXV) begin
                if (ndir < NDIR_MAX) begin
                    vec[ndir] = v[31:0];
                    ndir = ndir + 1;
                end else begin
                    $display("# WARNING directed set overflowed NDIR_MAX");
                end
            end
        end
    endtask

    // Drive one input and print the answer it produced.
    task drive(input [31:0] v);
        begin
            x = v;
            @(posedge clk);
            x_d = x;
            @(negedge clk);
            $display("%0d %0d", x_d, z);
        end
    endtask

    initial begin
        ndir = 0;

        // Fibonacci weights of the 46 digits: 1, 2, 3, 5, 8, ...
        fib[0] = 32'd1;
        fib[1] = 32'd2;
        for (i = 2; i < 46; i = i + 1) fib[i] = fib[i-1] + fib[i-2];

        // (a) the two smallest inputs
        push(33'd0);
        push(33'd1);

        // (b) every Fibonacci number below 2^32, minus one and plus one
        for (i = 0; i < 46; i = i + 1) begin
            push({1'b0, fib[i]} - 33'd1);
            push({1'b0, fib[i]});
            push({1'b0, fib[i]} + 33'd1);
        end

        // (c) long carry chains: alternating-Fibonacci partial sums.
        //     Four families -- growing from the bottom on even and on odd
        //     digit indices, and shrinking from the top likewise. Sums past
        //     2^32-1 are dropped by push, so the top-anchored families simply
        //     stop contributing once they leave the input range.
        acc = 33'd0;
        for (j = 0; j < 46; j = j + 2) begin
            acc = acc + {1'b0, fib[j]};
            push(acc - 33'd1); push(acc); push(acc + 33'd1);
        end
        acc = 33'd0;
        for (j = 1; j < 46; j = j + 2) begin
            acc = acc + {1'b0, fib[j]};
            push(acc - 33'd1); push(acc); push(acc + 33'd1);
        end
        acc = 33'd0;
        for (j = 45; j >= 0; j = j - 2) begin
            acc = acc + {1'b0, fib[j]};
            push(acc - 33'd1); push(acc); push(acc + 33'd1);
        end
        acc = 33'd0;
        for (j = 44; j >= 0; j = j - 2) begin
            acc = acc + {1'b0, fib[j]};
            push(acc - 33'd1); push(acc); push(acc + 33'd1);
        end

        // (d) the maximum and its neighbourhood
        push(33'd4294967295);
        push(33'd4294967294);
        push(33'd4294967293);
        push(33'd2147483648);
        push(33'd2147483647);

        $display("# zeck_reenc32 directed+random SAMPLE -- not exhaustive");
        $display("# directed=%0d random=%0d seed=%0h space=4294967296",
                 ndir, NRAND, SEED);

        // Prime the pipeline, then drive. x_d carries the input that produced
        // the z being printed.
        @(negedge clk);
        for (i = 0; i < ndir; i = i + 1) drive(vec[i]);

        // xorshift32, seeded once. Never emits 0; 0 is in the directed set.
        rnd = SEED;
        for (i = 0; i < NRAND; i = i + 1) begin
            rnd = rnd ^ (rnd << 13);
            rnd = rnd ^ (rnd >> 17);
            rnd = rnd ^ (rnd << 5);
            drive(rnd);
        end

        // $finish(0) rather than $finish: the default prints a banner on stdout,
        // and the oracle treats any unparsable line in the capture as a failure
        // instead of skipping it.
        $finish(0);
    end
endmodule
