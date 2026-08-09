`default_nettype none
module h_bram (input wire clk, input wire rst_n, output wire [7:0] led);
  reg [31:0] lfsr = 32'hACE1_1234;
  always @(posedge clk) lfsr <= !rst_n ? 32'hACE1_1234
                                       : {lfsr[30:0], lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
  reg [31:0] w; always @(posedge clk) w <= lfsr;
  wire [31:0] o;
  takum32_decode_bram u (.clk(clk), .t32(w), .fp32_out(o));
  reg [31:0] q; always @(posedge clk) q <= o;
  assign led = q[7:0] ^ q[31:24];
endmodule
