#!/bin/zsh
# The structural cost of non-closure, measured in the harness that produced the
# decoder table: isolated unit, EVERY output bit folded into the observed
# reduction, median of five placement seeds.
#
# The comparison is deliberately stacked against us. For the closed path we
# measure the WHOLE weight application. For the non-closed path we measure ONLY
# the transformation stage that non-closure forces -- none of the arithmetic
# that would sit on top of it. If the closed path is still smaller, the claim
# holds a fortiori.
NP=/Users/ssdm4/Desktop/PROJECTS/CLAUDE/t27/target/nextpnr-xilinx/build/nextpnr-xilinx
CDB=/Users/ssdm4/Desktop/PROJECTS/CLAUDE/video-ax7203/build_lcd_diag2/chipdb/xc7a200tfbg484.bin
run() {  # $1 name  $2 instance  $3 sources  $4 observed-width
cat > c_$1.v <<V
\`default_nettype none
module c_$1 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [$(($4-1)):0] o;
  $2
  reg [$(($4-1)):0] q;
  always @(posedge clk) q <= !rst_n ? {$4{1'b0}} : o;
  assign led = ^{q, 4'b0} ? (q[3:0] ^ q[$(($4-1)):$(($4-4))]) : 4'b0;
endmodule
V
yosys -q -p "read_verilog c_$1.v $3; synth_xilinx -flatten -nodsp -top c_$1 -json c_$1.json" > cy_$1.log 2>&1
[ -f c_$1.json ] || { echo "$1|СИНТЕЗ_НЕ_ПРОШЁЛ"; return; }
FS=""
for S in 1 2 3 4 5; do
  $NP --chipdb $CDB --xdc bench.xdc --json c_$1.json --seed $S --write /dev/null > cs_$1_$S.log 2>&1
  FS="$FS $(grep -oE "Max frequency for clock .[^']*.: [0-9.]+" cs_$1_$S.log|tail -1|grep -oE "[0-9.]+$")"
done
L=$(grep -oE "SLICE_LUTX: *[0-9]+" cs_$1_1.log|tail -1|grep -oE "[0-9]+$")
echo "$1|$L|$FS"
}
run phi16   "wire [15:0] oa,ob; phi_step #(.W(16)) u (.clk(clk),.dir(1'b0),.a(lf[15:0]),.b(lf[31:16]),.oa(oa),.ob(ob)); assign o = {oa,ob};" "phi_step.v" 32
run zeck16  "zeck_reenc16 u (.clk(clk),.x(lf[15:0]),.z(o));" "zeck_reenc16.v" 23
run phi32   "wire [31:0] oa,ob; phi_step #(.W(32)) u (.clk(clk),.dir(1'b0),.a(lf[31:0]),.b(lf[63:32]),.oa(oa),.ob(ob)); assign o = {oa,ob};" "phi_step.v" 64
run zeck32  "zeck_reenc32 u (.clk(clk),.x(lf[31:0]),.z(o));" "zeck_reenc32.v" 46
run zphi16  "wire [15:0] sa,sb; zphi_add #(.W(16)) u (.clk(clk),.a0(lf[15:0]),.b0(lf[31:16]),.a1(lf[47:32]),.b1(lf[63:48]),.sa(sa),.sb(sb)); assign o = {sa,sb};" "zphi_add.v" 32
run zphi32  "wire [31:0] sa,sb; zphi_add #(.W(32)) u (.clk(clk),.a0(lf[31:0]),.b0(lf[63:32]),.a1(lf[63:32]),.b1(lf[31:0]),.sa(sa),.sb(sb)); assign o = {sa,sb};" "zphi_add.v" 64
