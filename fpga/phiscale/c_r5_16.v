`default_nettype none
module c_r5_16 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [79:0] o;
  wire signed [15:0] y0,y1,y2,y3,y4; rpow5_step #(.W(16)) u (.clk(clk), .x0(lf[0+:16]), .x1(lf[11+:16]), .x2(lf[22+:16]), .x3(lf[0+:16]), .x4(lf[11+:16]), .o0(y0), .o1(y1), .o2(y2), .o3(y3), .o4(y4)); assign o = {y0,y1,y2,y3,y4};
  reg [79:0] q;
  always @(posedge clk) q <= !rst_n ? {80{1'b0}} : o;
  assign led = ^{q, 4'b0} ? (q[3:0] ^ q[79:76]) : 4'b0;
endmodule
