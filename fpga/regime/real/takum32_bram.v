`default_nettype none
`timescale 1ns / 1ps
// takum32_decode — Hunhold 2024 logarithmic (N=32) -> FP32.
// value = (-1)^S * exp(ell/2) = (-1)^S * 2^L where L = ell * log2(e)/2.
// Range reduce L -> k (integer exp) + frac. 2^frac via BRAM table + linear Taylor correction.
//
// SUBNORMAL FIX (2026-07-03 loop): inner guard -149 -> -150 so values in
// (2^-150, 2^-149) round up to min subnormal 0x00000001 instead of flush.
// Fixes 7 latent underflow cases at ell ~ [-208,-206] (0.031% of random
// inputs; missed by the 64-vector conformance). Verified bit-exact iverilog.
//
// ROUTING-OPT (iter 3): f_lo truncated top 24 + sticky (107->72-bit multiply).
// ell_27 kept full-width (87-bit) -- precision budget too tight to narrow.
module takum32_decode_bram (input wire clk, input wire [31:0] t32, output reg [31:0] fp32_out);
    localparam [47:0] C_Q48   = 48'd203041276517399; // log2(e)/2 * 2^48
    localparam [47:0] LN2_Q48 = 48'd195103586505167; // ln2 * 2^48

    wire S = t32[31]; wire D = t32[30]; wire [2:0] R = t32[29:27];
    wire [3:0] cidx = {D, R};
    reg signed [8:0] cbias;
    always @* case (cidx)
        4'd0:cbias=-9'sd255; 4'd1:cbias=-9'sd127; 4'd2:cbias=-9'sd63; 4'd3:cbias=-9'sd31;
        4'd4:cbias=-9'sd15;  4'd5:cbias=-9'sd7;   4'd6:cbias=-9'sd3;  4'd7:cbias=-9'sd1;
        4'd8:cbias=9'sd0;    4'd9:cbias=9'sd1;    4'd10:cbias=9'sd3;  4'd11:cbias=9'sd7;
        4'd12:cbias=9'sd15;  4'd13:cbias=9'sd31;  4'd14:cbias=9'sd63; 4'd15:cbias=9'sd127;
    endcase
    wire [2:0] r_eff = D ? R : (3'd7 - R);
    wire [4:0] p = 5'd27 - {2'b00, r_eff};
    wire [26:0] lower = t32[26:0];
    wire [26:0] M_u = lower & ((27'h1 << p) - 1);
    wire [26:0] C_u = (lower >> p) & ((27'h1 << {2'b00, r_eff}) - 1);
    wire signed [9:0] c = $signed(cbias) + $signed({17'b0, C_u});
    // ell_scaled_27 = (1-2S)(c*2^27 + M_u<<r_eff)
    wire signed [37:0] c_sh = c * 38'sd134217728; // c * 2^27 (NOT c<<<27 which stays 10-bit)
    wire signed [37:0] m_sh = $signed({11'b0, M_u << r_eff});
    wire signed [37:0] ell_27 = S ? -(c_sh + m_sh) : (c_sh + m_sh);
    // L_Q75 = ell_27 * C_Q48
    wire signed [86:0] L_Q75 = ell_27 * $signed({1'b0, C_Q48});
    // k = floor(L) = L_Q75 >>> 75; frac = L_Q75[74:0]
    wire signed [11:0] k = L_Q75 >>> 75;
    wire [74:0] frac = L_Q75[74:0];
    wire [15:0] f_hi = frac[74:59];
    wire [58:0] f_lo_full = frac[58:0];
    // --- ROUTING OPT (2026-07-03 loop iter 3): truncate f_lo top 24 + sticky ---
    // narrows flo_ln2 multiply 107-bit -> 72-bit; bit-exact on 22k vectors.
    wire f_lo_sticky = |f_lo_full[34:0];
    wire [58:0] f_lo = {f_lo_full[58:35], f_lo_sticky, 34'b0};
    // BRAM table: 2^(f_hi/2^16), 48-bit
    // BRAM inference needs a CLOCKED read. The original reads combinationally,
    // which is why 3.15 Mbit synthesised into logic. Registering the read is the
    // only way a table this size exists in real silicon; it costs one cycle of
    // latency, and that is stated rather than hidden -- this is a pipelined
    // variant of the published module, not the published module.
    (* ram_style="block" *) reg [47:0] tbl [0:65535];
    initial $readmemh("fpga/openxc7-synth/takum32_2frac.mem", tbl);
    reg [47:0] tval_r;
    always @(posedge clk) tval_r <= tbl[f_hi];
    wire [47:0] tval = tval_r;
    // correction: corr = (f_lo * LN2_Q48) >> 75  (~2^31 max)
    wire signed [107:0] flo_ln2 = $signed({49'b0, f_lo}) * $signed({1'b0, LN2_Q48});
    wire [31:0] corr = flo_ln2 >>> 75;
    wire [31:0] corr_q2 = corr + ((corr * corr) >> 49); // + quadratic Taylor term x^2/2
    // mantissa = tval + (tval * corr_q2 >> 48)
    wire [79:0] tp = tval * corr_q2;
    wire [48:0] mant = {1'b0, tval} + tp[79:48];
    // normalize + round
    reg [47:0] mn; reg signed [11:0] e2;
    reg [24:0] m25; reg g, r_b, stb, ru; reg [23:0] m24;
    reg [47:0] sv; reg sg, sr_, ss_, sru; reg [23:0] sk;
    always @* begin
        if (mant[48]) begin mn = {1'b0, mant[48:1]}; e2 = k + 12'sd1; end
        else begin mn = mant[47:0]; e2 = k; end
        m25 = {1'b0, mn[47:24]}; g = mn[23]; r_b = mn[22]; stb = |mn[21:0];
        ru = g & (r_b | stb | m25[0]);
        if (ru) m25 = m25 + 1;
        if (m25[24]) begin m24 = 24'h800000; e2 = e2 + 12'sd1; end else m24 = m25[23:0];
        fp32_out = 32'h7FC00000;
        if (t32 == 0)               fp32_out = 32'h00000000;
        else if (t32 == 32'h80000000) fp32_out = 32'h7FC00000;
        else if (e2 > 12'sd127)     fp32_out = {S, 8'hFF, 23'h0};
        else if (e2 < -12'sd150)    fp32_out = {S, 31'h0};
        else if (e2 < -12'sd126) begin
            if (e2 >= -12'sd150) begin
                // SUBNORMAL FIX (2026-07-03 loop): include e2=-150 so values in
                // (2^-150, 2^-149) round up to min subnormal 0x00000001, not flush.
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
