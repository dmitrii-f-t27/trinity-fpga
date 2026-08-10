`default_nettype none
module h320 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [319:0] lf = {2{160'h1234_5678_9ABC_DEF0_0FED_CBA9_8765_4321_DEAD_BEEF}};
  always @(posedge clk) lf <= !rst_n ? {2{160'h1234_5678_9ABC_DEF0_0FED_CBA9_8765_4321_DEAD_BEEF}}
                                     : {lf[318:0], lf[319]^lf[318]^lf[310]^lf[295]};
  reg signed [39:0] q;
  always @(posedge clk) q <= !rst_n ? 0 : lf[39:0];
  assign led = ^{q, 4'b0} ? (q[3:0] ^ q[39:36]) : 4'b0;
endmodule
