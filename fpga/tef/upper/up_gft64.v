`default_nettype none
module up_gft64 (input wire clk, input wire rst_n, output wire [7:0] led);
  reg [63:0] lfsr = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lfsr <= !rst_n ? 64'h1234_5678_9ABC_DEF0
                                       : {lfsr[62:0], lfsr[63]^lfsr[62]^lfsr[60]^lfsr[59]};
  wire [255:0] wide = {lfsr, ~lfsr, lfsr, ~lfsr};
  reg [11:0] ao, bo; reg [55:0] am, bm;
  always @(posedge clk) begin
    ao <= wide[11:0]; bo <= wide[23:12];
    am <= wide[55:0]; bm <= wide[63:8];
  end
  wire [11:0] o; wire [55:0] m;
  tef_mul_wp #(.MANT_W(56), .OFF_W(12), .BIAS(1093), .OFFSET_MAX(2186)) u
    (.clk(clk), .rst_n(rst_n), .a_off(ao), .a_mant(am), .b_off(bo), .b_mant(bm),
     .out_off(o), .out_mant(m));
  assign led = o[7:0] ^ m[7:0];
endmodule
