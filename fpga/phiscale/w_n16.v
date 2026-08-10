`default_nettype none
module w_n16 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [127:0] lf = 128'h1234_5678_9ABC_DEF0_0FED_CBA9_8765_4321;
  always @(posedge clk) lf <= !rst_n ? 128'h1234_5678_9ABC_DEF0_0FED_CBA9_8765_4321
                                     : {lf[126:0], lf[127]^lf[126]^lf[120]^lf[110]};
  wire signed [15:0] aa, bb;
  tern_node #(.N(16), .W(8), .ACC(16)) u (.clk(clk), .x(lf[127:0]),
      .w(lf[127:96]), .acc_a(aa), .acc_b(bb));
  reg signed [31:0] q;
  always @(posedge clk) q <= !rst_n ? 0 : {aa, bb};
  assign led = ^{q, 4'b0} ? (q[3:0] ^ q[31:28]) : 4'b0;
endmodule
