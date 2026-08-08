#!/bin/zsh
NP=/Users/ssdm4/Desktop/PROJECTS/CLAUDE/t27/target/nextpnr-xilinx/build/nextpnr-xilinx
CDB=/Users/ssdm4/Desktop/PROJECTS/CLAUDE/video-ax7203/build_lcd_diag2/chipdb/xc7a200tfbg484.bin
# согласованные верхние ступени: M = N-1-Et, OFF_W = ceil(log2 3^Et)
run() {  # $1=имя $2=M $3=Et
  M=$2; Et=$3
  OM=$(python3 -c "print(3**$Et-1)"); BI=$(python3 -c "print((3**$Et-1)//2)")
  OW=$(python3 -c "import math;print(max(1,($OM).bit_length()))")
  cat > up_$1.v <<V
\`default_nettype none
module up_$1 (input wire clk, input wire rst_n, output wire [7:0] led);
  reg [63:0] lfsr = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lfsr <= !rst_n ? 64'h1234_5678_9ABC_DEF0
                                       : {lfsr[62:0], lfsr[63]^lfsr[62]^lfsr[60]^lfsr[59]};
  wire [255:0] wide = {lfsr, ~lfsr, lfsr, ~lfsr};
  reg [$((OW-1)):0] ao, bo; reg [$((M-1)):0] am, bm;
  always @(posedge clk) begin
    ao <= wide[$((OW-1)):0]; bo <= wide[$((2*OW-1)):$OW];
    am <= wide[$((M-1)):0]; bm <= wide[$((M+7)):8];
  end
  wire [$((OW-1)):0] o; wire [$((M-1)):0] m;
  gft_mul_wp #(.MANT_W($M), .OFF_W($OW), .BIAS($BI), .OFFSET_MAX($OM)) u
    (.clk(clk), .rst_n(rst_n), .a_off(ao), .a_mant(am), .b_off(bo), .b_mant(bm),
     .out_off(o), .out_mant(m));
  assign led = o[7:0] ^ m[7:0];
endmodule
V
  yosys -q -p "read_verilog up_$1.v gft_mul_wp.v; synth_xilinx -flatten -nodsp -top up_$1 -json up_$1.json" > ys_$1.log 2>&1
  $NP --chipdb $CDB --xdc bench.xdc --json up_$1.json --write up_$1_r.json > up_$1.log 2>&1
  L=$(grep -oE "SLICE_LUTX: *[0-9]+" up_$1.log|tail -1|grep -oE "[0-9]+")
  F=$(grep -oE "Max frequency for clock '[^']*': [0-9.]+" up_$1.log|tail -1|grep -oE "[0-9.]+$")
  echo "$1 M=$M Et=$Et LUT=$L Fmax=$F"
}
run gft64 56 7
run gft128 119 8
