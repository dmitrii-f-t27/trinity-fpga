`default_nettype none
module v_n32 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [319:0] lf = {2{160'h1234_5678_9ABC_DEF0_0FED_CBA9_8765_4321_DEAD_BEEF}};
  always @(posedge clk) lf <= !rst_n ? {2{160'h1234_5678_9ABC_DEF0_0FED_CBA9_8765_4321_DEAD_BEEF}}
                                     : {lf[318:0], lf[319]^lf[318]^lf[310]^lf[295]};
  wire signed [19:0] aa, bb;
  tern_node2 #(.N(32), .W(8), .ACC(20)) u (.clk(clk), .x(lf[255:0]),
      .w(lf[319:256]), .acc_a(aa), .acc_b(bb));
  reg signed [39:0] q;
  always @(posedge clk) q <= !rst_n ? 0 : {aa, bb};
  assign led = ^{q, 4'b0} ? (q[3:0] ^ q[39:36]) : 4'b0;
endmodule
