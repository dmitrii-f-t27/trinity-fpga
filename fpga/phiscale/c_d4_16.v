`default_nettype none
module c_d4_16 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [63:0] o;
  wire signed [15:0] a,b,c,d; deg4_step #(.W(16)) u (.clk(clk),.x0(lf[15:0]),.x1(lf[31:16]),.x2(lf[47:32]),.x3(lf[63:48]),.o0(a),.o1(b),.o2(c),.o3(d)); assign o = {a,b,c,d};
  reg [63:0] q;
  always @(posedge clk) q <= !rst_n ? {64{1'b0}} : o;
  assign led = ^{q, 4'b0} ? (q[3:0] ^ q[63:60]) : 4'b0;
endmodule
