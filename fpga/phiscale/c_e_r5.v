`default_nettype none
module c_e_r5 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire signed [19:0] cw; wire zw, nw;
  elem_r5  u (.clk(clk), .code(lf[4:0]), .coord(cw), .zero(zw), .neg(nw));
  reg [21:0] q;
  always @(posedge clk) q <= !rst_n ? 0 : {cw, zw, nw};
  assign led = ^{q, 4'b0} ? (q[3:0] ^ q[21:18]) : 4'b0;
endmodule
