#!/bin/zsh
NP=/Users/ssdm4/Desktop/PROJECTS/CLAUDE/t27/target/nextpnr-xilinx/build/nextpnr-xilinx
CDB=/Users/ssdm4/Desktop/PROJECTS/CLAUDE/video-ax7203/build_lcd_diag2/chipdb/xc7a200tfbg484.bin
for M in 32 40 48 70 90; do
  cat > sw_$M.v <<V
\`default_nettype none
module sw_$M (input wire clk, input wire rst_n, output wire [7:0] led);
  reg [63:0] lfsr = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lfsr <= !rst_n ? 64'h1234_5678_9ABC_DEF0
                                       : {lfsr[62:0], lfsr[63]^lfsr[62]^lfsr[60]^lfsr[59]};
  wire [255:0] wide = {lfsr, ~lfsr, lfsr, ~lfsr};
  reg [6:0] ao, bo; reg [$((M-1)):0] am, bm;
  always @(posedge clk) begin
    ao <= wide[6:0]; bo <= wide[13:7]; am <= wide[$((M-1)):0]; bm <= wide[$((M+7)):8];
  end
  wire [6:0] o; wire [$((M-1)):0] m;
  tef_mul_wp #(.MANT_W($M), .OFF_W(7), .BIAS(40), .OFFSET_MAX(80)) u
    (.clk(clk), .rst_n(rst_n), .a_off(ao), .a_mant(am), .b_off(bo), .b_mant(bm),
     .out_off(o), .out_mant(m));
  assign led = o[6:0] ^ m[7:0];
endmodule
V
  yosys -q -p "read_verilog sw_$M.v tef_mul_wp.v; synth_xilinx -flatten -nodsp -top sw_$M -json sw_$M.json" >/dev/null 2>&1
  $NP --chipdb $CDB --xdc bench.xdc --json sw_$M.json --write sw_${M}_r.json > sw_$M.log 2>&1
  L=$(grep -oE "SLICE_LUTX: *[0-9]+" sw_$M.log|tail -1|grep -oE "[0-9]+")
  F=$(grep -oE "Max frequency for clock '[^']*': [0-9.]+" sw_$M.log|tail -1|grep -oE "[0-9.]+$")
  echo "M=$M LUT=${L:-разводка не сошлась} Fmax=${F:-—}"
done
