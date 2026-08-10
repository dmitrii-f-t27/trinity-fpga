// Diagnostic twin of c_sgld32: SAME supergold_step, only the operand routing changes.
//
// c_sgld32 copies c_plas32's slice assignment literally, which is a trap here.
// supergold_step adds b+c, and in that wrapper b=lf[63:32] and c={lf[15:0],lf[47:32]}
// share their low half (both are lf[47:32]), so the low 16 bits of the sum are a
// free shift and the carry chain is effectively 16 bits, not 32. plastic_step adds
// a+c, whose operands do not alias, so it pays the full ripple. Any Fmax gap between
// the two would then be an artefact of the harness, not of the ladder.
//
// Here b and c are the operand pair c_plas32's adder actually sees, so the adder is
// bit-for-bit the same problem. If this matches plastic's Fmax, the gap was the harness.
`default_nettype none
module c_sgld32b (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [95:0] o;
  wire signed [31:0] oa,ob,oc; supergold_step #(.W(32)) u (.clk(clk),.a(lf[63:32]),.b(lf[31:0]),.c({lf[15:0],lf[47:32]}),.oa(oa),.ob(ob),.oc(oc)); assign o = {oa,ob,oc};
  reg [95:0] q;
  always @(posedge clk) q <= !rst_n ? {96{1'b0}} : o;
  assign led = ^{q, 4'b0} ? (q[3:0] ^ q[95:92]) : 4'b0;
endmodule
