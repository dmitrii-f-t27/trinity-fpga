// gf_decode_param_pipe.v  -- 2-stage PIPELINED variant of gf_decode_param.v
// -----------------------------------------------------------------------------
// Purpose (Trinity Catalog-100, horizon-B routing prep, 2026-07-24):
//   gf24 (BIAS=255) and gf32 (BIAS=2047) decode fail nextpnr routing on
//   AX7203 (XC7A200T) when synthesized from the pure-combinational
//   gf_decode_param.v (no-flatten CI = FAILURE, runs 28773511637 / 28773514467).
//   Root cause is NOT a giant LUT table (unlike takum, which the split-BRAM
//   trick fixed) but the DEPTH of one combinational cloud: variable barrel
//   shift (up to ~40-bit) + dynamic sticky-mask + CLZ + rounding, all in a
//   single always@(*). This module breaks that cloud into 2 registered
//   stages to shorten the critical path so the placer/router can meet timing
//   and fit routing.
//
//   Semantics are BIT-IDENTICAL to gf_decode_param.v (same 5-class decode
//   law, same iverilog-proven fixes: widen-before-shift #1, [23:0] sub_shifted
//   OOB-read #2). This file only adds pipeline registers; it does NOT change
//   any arithmetic. Latency = 2 clocks (result valid 2 cycles after gf_in).
//
//   Status: [verified SW на iverilog] once tb_gf_decode_param_pipe.v passes
//   against the golden Fraction oracle. Synth/PnR/flash on AX7203 remains
//   [ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ] -- pipelining is a HYPOTHESIS for the
//   routing fix, provable only on the board. iverilog only proves FUNCTION.
//
// Author: Vasilev (gHashTag), ORCID 0009-0008-4294-6159, admin@t27.ai.
// -----------------------------------------------------------------------------

module gf_decode_param_pipe #(
    parameter integer N    = 24,
    parameter integer E    = 8,
    parameter integer M    = 15,
    parameter integer BIAS = 255
) (
    input  wire                 clk,
    input  wire                 rst_n,     // sync active-low
    input  wire [N-1:0]         gf_in,
    output wire [31:0]          fp32_out,  // valid 2 clocks after gf_in
    output wire                 is_nan_o,
    output wire                 is_inf_o,
    output wire                 is_zero_o,
    output wire                 is_subnormal_o
);
    localparam [E-1:0] EXP_MAX          = {E{1'b1}};
    localparam integer FP32_EBIAS       = 127;
    localparam integer FP32_MANT        = 23;
    localparam integer FP32_MIN_NORM_EXP= -126;
    localparam integer FP32_SUB_LSB_EXP = -149;
    localparam integer EXP_CALC_W       = 40;

    // ============================ STAGE 0 (comb) ============================
    // Field extraction + classification + true_exp + shift computation.
    wire               sign0   = gf_in[N-1];
    wire [E-1:0]       exp0    = gf_in[N-2 -: E];
    wire [M-1:0]       mant0   = gf_in[M-1:0];

    wire is_exp_zero0  = (exp0 == {E{1'b0}});
    wire is_exp_max0   = (exp0 == EXP_MAX);
    wire is_mant_zero0 = (mant0 == {M{1'b0}});

    wire cls_zero0      = is_exp_zero0 &&  is_mant_zero0;
    wire cls_subnormal0 = is_exp_zero0 && !is_mant_zero0;
    wire cls_inf0       = is_exp_max0  &&  is_mant_zero0;
    wire cls_nan0       = is_exp_max0  && !is_mant_zero0;

    function integer clz_m;
        input [M-1:0] v;
        integer i;
        begin
            clz_m = M;
            for (i = 0; i < M; i = i + 1)
                if (v[M-1-i] && (clz_m == M)) clz_m = i;
        end
    endfunction
    wire signed [31:0] lzc0 = clz_m(mant0);

    wire signed [EXP_CALC_W-1:0] sub_true_exp0 =
        ($signed(1) - BIAS) - (lzc0 + 32'sd1);
    wire [M-1:0] sub_frac0 = (mant0 << (lzc0[7:0] + 8'd1));
    wire signed [EXP_CALC_W-1:0] norm_true_exp0 =
        $signed({1'b0, exp0}) - BIAS;

    wire signed [EXP_CALC_W-1:0] pack_true_exp0 = cls_subnormal0 ? sub_true_exp0 : norm_true_exp0;
    wire [M-1:0]                 pack_frac0     = cls_subnormal0 ? sub_frac0      : mant0;

    // ---- Stage 0/1 pipeline registers ----
    reg                          sign1;
    reg                          cls_zero1, cls_subnormal1, cls_inf1, cls_nan1;
    reg signed [EXP_CALC_W-1:0]  pack_true_exp1;
    reg [M-1:0]                  pack_frac1;

    always @(posedge clk) begin
        if (!rst_n) begin
            sign1 <= 1'b0; cls_zero1 <= 1'b0; cls_subnormal1 <= 1'b0;
            cls_inf1 <= 1'b0; cls_nan1 <= 1'b0;
            pack_true_exp1 <= {EXP_CALC_W{1'b0}}; pack_frac1 <= {M{1'b0}};
        end else begin
            sign1          <= sign0;
            cls_zero1      <= cls_zero0;
            cls_subnormal1 <= cls_subnormal0;
            cls_inf1       <= cls_inf0;
            cls_nan1       <= cls_nan0;
            pack_true_exp1 <= pack_true_exp0;
            pack_frac1     <= pack_frac0;
        end
    end

    // ============================ STAGE 1 (comb) ============================
    // Barrel shift + rounding + FP32 pack (the deep path), now on registered
    // inputs so the critical path is halved.

    // ---- Attempt 1: FP32 NORMAL (widen-before-shift, fix #1) ----
    localparam integer WIDE = (M > FP32_MANT) ? M : FP32_MANT;
    wire [WIDE:0] norm_widen_result;
    generate
        if (M <= FP32_MANT) begin : g_widen
            wire [WIDE:0] pf_wide = { {(WIDE-M+1){1'b0}}, pack_frac1 };
            assign norm_widen_result = pf_wide << (FP32_MANT - M);
        end else begin : g_narrow
            wire                 g_bit  = pack_frac1[M-FP32_MANT-1];
            wire                 s_bit  = |pack_frac1[M-FP32_MANT-2:0];
            wire [FP32_MANT-1:0] trunc  = pack_frac1[M-1 -: FP32_MANT];
            wire round_up = g_bit && (s_bit || trunc[0]);
            wire [FP32_MANT:0] rounded = {1'b0, trunc} + (round_up ? 1'b1 : 1'b0);
            assign norm_widen_result = { {(WIDE-FP32_MANT){1'b0}}, rounded };
        end
    endgenerate
    wire        norm_carry  = norm_widen_result[FP32_MANT];
    wire [22:0] norm_mant23 = norm_widen_result[22:0];
    wire signed [EXP_CALC_W-1:0] norm_exp_final = pack_true_exp1 + norm_carry + FP32_EBIAS;

    wire is_fp32_normal_candidate = (pack_true_exp1 >= FP32_MIN_NORM_EXP);
    wire norm_overflow  = is_fp32_normal_candidate && (norm_exp_final >= 255);
    wire norm_takes_normal_path = is_fp32_normal_candidate && !norm_overflow && (norm_exp_final >= 1);
    wire signed [EXP_CALC_W-1:0] corrected_true_exp = pack_true_exp1 + norm_carry;

    // ---- Attempt 2: FP32 SUBNORMAL packer (gradual underflow) ----
    wire signed [EXP_CALC_W-1:0] eff_true_exp_for_sub =
        is_fp32_normal_candidate ? corrected_true_exp : pack_true_exp1;
    wire [M:0] full_sig = {1'b1, pack_frac1};
    wire signed [EXP_CALC_W-1:0] shift_s = M - eff_true_exp_for_sub + FP32_SUB_LSB_EXP;

    localparam integer MAXSH = M + 8;
    wire [31:0] shift_clamped = (shift_s < 0) ? 32'd0 :
                                (shift_s > MAXSH) ? MAXSH[31:0] : shift_s[31:0];

    // [23:0] width per iverilog fix #2 (OOB read on gf24/gf32)
    wire [23:0] sub_shifted = (shift_s <= 0) ? (full_sig << (-shift_s))
                                              : (full_sig >> shift_clamped);
    wire [M:0]  sub_lost_mask = (shift_clamped == 0) ? {(M+1){1'b0}} : ({(M+1){1'b1}} >> (M+1-shift_clamped));
    wire [M:0]  sub_lost    = full_sig & sub_lost_mask;
    wire        sub_guard   = (shift_clamped >= 1) ? sub_lost[shift_clamped-1] : 1'b0;
    wire [M:0]  sub_sticky_mask = (shift_clamped >= 1) ? ({(M+1){1'b1}} >> (M+2-shift_clamped)) : {(M+1){1'b0}};
    wire        sub_sticky  = (shift_clamped >= 1) ? (|(sub_lost & sub_sticky_mask)) : 1'b0;

    wire [24:0] sub_mant_pre = {2'b0, sub_shifted[22:0]};
    wire        sub_round_up = sub_guard && (sub_sticky || sub_shifted[0]);
    wire [24:0] sub_mant_rounded = sub_mant_pre + (sub_round_up ? 25'd1 : 25'd0);
    wire        sub_carry_to_normal = sub_mant_rounded[23];
    wire [22:0] sub_mant23 = sub_mant_rounded[22:0];

    localparam [31:0] FP32_QNAN    = 32'h7FC00001;
    localparam [31:0] FP32_POS_INF = 32'h7F800000;
    localparam [31:0] FP32_NEG_INF = 32'hFF800000;

    reg [31:0] fp32_c;
    always @(*) begin
        fp32_c = 32'h00000000;
        if (cls_nan1)            fp32_c = FP32_QNAN;
        else if (cls_inf1)       fp32_c = sign1 ? FP32_NEG_INF : FP32_POS_INF;
        else if (cls_zero1)      fp32_c = {sign1, 31'b0};
        else if (norm_overflow)  fp32_c = sign1 ? FP32_NEG_INF : FP32_POS_INF;
        else if (norm_takes_normal_path)
                                 fp32_c = {sign1, norm_exp_final[7:0], norm_mant23};
        else begin
            if (sub_carry_to_normal) fp32_c = {sign1, 8'd1, 23'b0};
            else                     fp32_c = {sign1, 8'b0, sub_mant23};
        end
    end

    // ---- Stage 1/2 output register (latency = 2) ----
    reg [31:0] fp32_q;
    reg        nan_q, inf_q, zero_q, sub_q;
    always @(posedge clk) begin
        if (!rst_n) begin
            fp32_q <= 32'b0; nan_q <= 1'b0; inf_q <= 1'b0; zero_q <= 1'b0; sub_q <= 1'b0;
        end else begin
            fp32_q <= fp32_c;
            nan_q  <= cls_nan1;
            inf_q  <= cls_inf1;
            zero_q <= cls_zero1;
            sub_q  <= cls_subnormal1;
        end
    end

    assign fp32_out       = fp32_q;
    assign is_nan_o       = nan_q;
    assign is_inf_o       = inf_q;
    assign is_zero_o      = zero_q;
    assign is_subnormal_o = sub_q;

endmodule
