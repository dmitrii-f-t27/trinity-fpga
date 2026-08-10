`default_nettype none
module c_r8_16 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [127:0] o;
  wire signed [15:0] z0,z1,z2,z3,z4,z5,z6,z7; rpow8_step #(.W(16)) u (.clk(clk), .x0(lf[0+:16]), .x1(lf[7+:16]), .x2(lf[14+:16]), .x3(lf[21+:16]), .x4(lf[28+:16]), .x5(lf[35+:16]), .x6(lf[42+:16]), .x7(lf[0+:16]), .o0(z0), .o1(z1), .o2(z2), .o3(z3), .o4(z4), .o5(z5), .o6(z6), .o7(z7)); assign o = {z0,z1,z2,z3,z4,z5,z6,z7};
  reg [127:0] q;
  always @(posedge clk) q <= !rst_n ? {128{1'b0}} : o;
  assign led = ^{q, 4'b0} ? (q[3:0] ^ q[127:124]) : 4'b0;
endmodule
