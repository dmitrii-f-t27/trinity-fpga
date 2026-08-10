`default_nettype none
module c_plas16 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [47:0] o;
  wire signed [15:0] oa,ob,oc; plastic_step #(.W(16)) u (.clk(clk),.a(lf[15:0]),.b(lf[31:16]),.c(lf[47:32]),.oa(oa),.ob(ob),.oc(oc)); assign o = {oa,ob,oc};
  reg [47:0] q;
  always @(posedge clk) q <= !rst_n ? {48{1'b0}} : o;
  assign led = ^{q, 4'b0} ? (q[3:0] ^ q[47:44]) : 4'b0;
endmodule
