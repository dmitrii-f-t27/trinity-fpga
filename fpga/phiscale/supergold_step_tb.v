// Dumps 4000 random (a,b,c) -> (oa,ob,oc) pairs from supergold_step so the
// psi-map can be checked OUTSIDE the RTL, against an independent computation.
// Inputs are shifted right by 2 so b+c cannot overflow 32-bit signed and the
// check tests the map, not the wrap behaviour.
`default_nettype none
module supergold_step_tb;
    reg clk = 0;
    reg signed [31:0] a, b, c;
    wire signed [31:0] oa, ob, oc;
    integer i, seed;
    supergold_step #(.W(32)) u (.clk(clk), .a(a), .b(b), .c(c),
                                .oa(oa), .ob(ob), .oc(oc));
    initial begin
        seed = 32'h5EED_0001;
        for (i = 0; i < 4000; i = i + 1) begin
            a = $random(seed) >>> 2;
            b = $random(seed) >>> 2;
            c = $random(seed) >>> 2;
            #1 clk = 1; #1 clk = 0;
            $display("%0d %0d %0d %0d %0d %0d", a, b, c, oa, ob, oc);
        end
        $finish;
    end
endmodule
