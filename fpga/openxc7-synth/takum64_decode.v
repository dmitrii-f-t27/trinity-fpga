`default_nettype none
`timescale 1ns / 1ps
// takum64_decode — Hunhold 2024 logarithmic (N=64) -> FP32. value = (-1)^S * exp(ell/2).
// 2^L decomposition (same as takum32, wider). 2^frac via BRAM table + quadratic Taylor.
module takum64_decode (input wire [63:0] t64, output reg [31:0] fp32_out);
    localparam [47:0] C_Q48   = 48'd203041276517399;
    localparam [47:0] LN2_Q48 = 48'd195103586505167;
    localparam PMAX = 59;

    wire S = t64[63]; wire D = t64[62]; wire [2:0] R = t64[61:59];
    wire [3:0] cidx = {D, R};
    reg signed [8:0] cbias;
    always @* case (cidx)
        4'd0:cbias=-9'sd255; 4'd1:cbias=-9'sd127; 4'd2:cbias=-9'sd63; 4'd3:cbias=-9'sd31;
        4'd4:cbias=-9'sd15;  4'd5:cbias=-9'sd7;   4'd6:cbias=-9'sd3;  4'd7:cbias=-9'sd1;
        4'd8:cbias=9'sd0;    4'd9:cbias=9'sd1;    4'd10:cbias=9'sd3;  4'd11:cbias=9'sd7;
        4'd12:cbias=9'sd15;  4'd13:cbias=9'sd31;  4'd14:cbias=9'sd63; 4'd15:cbias=9'sd127;
    endcase
    wire [2:0] r_eff = D ? R : (3'd7 - R);
    wire [6:0] p = PMAX - {4'b0, r_eff};
    wire [58:0] lower = t64[58:0];
    wire [58:0] M_u = lower & ((59'h1 << p) - 1);
    wire [58:0] C_u = (lower >> p) & ((59'h1 << {3'b0, r_eff}) - 1);
    wire signed [9:0] c = $signed(cbias) + $signed({49'b0, C_u});
    wire signed [69:0] c_sh = c * 70'sd576460752303423488; // c * 2^59
    wire signed [69:0] m_sh = $signed({11'b0, M_u << r_eff});
    wire signed [69:0] ell_59 = S ? -(c_sh + m_sh) : (c_sh + m_sh);
    wire signed [118:0] L_Q107 = ell_59 * $signed({1'b0, C_Q48});
    wire signed [12:0] k = L_Q107 >>> 107;
    wire [106:0] frac = L_Q107[106:0];
    wire [15:0] f_hi = frac[106:91];
    wire [90:0] f_lo = frac[90:0];
    reg [47:0] tbl [0:65535];
    initial $readmemh("fpga/openxc7-synth/takum32_2frac.mem", tbl); // SAME table as takum32
    wire [47:0] tval = tbl[f_hi];
    wire signed [139:0] flo_ln2 = $signed({49'b0, f_lo}) * $signed({1'b0, LN2_Q48});
    wire [31:0] corr = flo_ln2 >>> 107;
    wire [31:0] corr_q2 = corr + ((corr * corr) >> 49);
    wire [79:0] tp = tval * corr_q2;
    wire [48:0] mant = {1'b0, tval} + tp[79:48];
    reg [47:0] mn; reg signed [12:0] e2;
    reg [24:0] m25; reg g, r_b, stb, ru; reg [23:0] m24;
    reg [47:0] sv; reg sg, sr_, ss_, sru; reg [23:0] sk;
    always @* begin
        if (mant[48]) begin mn = {1'b0, mant[48:1]}; e2 = k + 13'sd1; end
        else begin mn = mant[47:0]; e2 = k; end
        m25 = {1'b0, mn[47:24]}; g = mn[23]; r_b = mn[22]; stb = |mn[21:0];
        ru = g & (r_b | stb | m25[0]);
        if (ru) m25 = m25 + 1;
        if (m25[24]) begin m24 = 24'h800000; e2 = e2 + 13'sd1; end else m24 = m25[23:0];
        fp32_out = 32'h7FC00000;
        if (t64 == 0)               fp32_out = 32'h00000000;
        else if (t64 == 64'h8000000000000000) fp32_out = 32'h7FC00000;
        else if (e2 > 13'sd127)     fp32_out = {S, 8'hFF, 23'h0};
        else if (e2 < -13'sd150)    fp32_out = {S, 31'h0};
        else if (e2 < -13'sd126) begin
            if (e2 >= -13'sd149) begin
                sv = mn >> (-e2 - 102);
                sg = ((-e2 - 102) >= 1) ? ((mn >> ((-e2 - 102) - 1)) & 1) : 0;
                sr_ = ((-e2 - 102) >= 2) ? ((mn >> ((-e2 - 102) - 2)) & 1) : 0;
                ss_ = ((-e2 - 102) >= 3) ? |(mn & ((48'h1 << ((-e2 - 102) - 2)) - 1)) : 0;
                sru = sg & (sr_ | ss_ | sv[0]);
                sk = {1'b0, sv[22:0]} + (sru ? 24'd1 : 24'd0);
                if (sk >= 24'h800000) fp32_out = {S, 8'h01, 23'h0};
                else if (sk == 0) fp32_out = {S, 31'h0};
                else fp32_out = {S, 8'h00, sk[22:0]};
            end else fp32_out = {S, 31'h0};
        end else fp32_out = {S, e2[7:0] + 8'd127, m24[22:0]};
    end
endmodule
`default_nettype none
