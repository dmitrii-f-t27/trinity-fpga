`default_nettype none
module c_sgld32 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [95:0] o;
  wire signed [31:0] oa,ob,oc; supergold_step #(.W(32)) u (.clk(clk),.a(lf[31:0]),.b(lf[63:32]),.c({lf[15:0],lf[47:32]}),.oa(oa),.ob(ob),.oc(oc)); assign o = {oa,ob,oc};
  reg [95:0] q;
  always @(posedge clk) q <= !rst_n ? {96{1'b0}} : o;
  assign led = ^{q, 4'b0} ? (q[3:0] ^ q[95:92]) : 4'b0;
endmodule
