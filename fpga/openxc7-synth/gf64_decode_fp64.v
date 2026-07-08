`default_nettype none
`timescale 1ns / 1ps
// gf64_decode_fp64 — GoldenFloat64 (N=64, E=24, M=39, BIAS=8388607) -> FP64 decode.
// Faithful: M=39 < FP64_MANT=52, so mantissa widens without truncation.
// Parametric FP64 packer handles normal/subnormal/Inf/NaN for FP64 range.
module gf64_decode_fp64 (
    input  wire [63:0]   gf64_in,
    output reg  [63:0]   fp64_out,
    output reg           is_nan_o,
    output reg           is_inf_o,
    output reg           is_zero_o,
    output reg           is_subnormal_o
);
    localparam [23:0] EXP_MAX = {24{1'b1}};
    localparam integer FP64_EBIAS      = 1023;
    localparam integer FP64_MANT       = 52;
    localparam integer FP64_MIN_NORM_EXP = -1022;
    localparam integer FP64_SUB_LSB_EXP  = -1074;

    localparam [63:0] FP64_QNAN    = 64'h7FF8000000000001;
    localparam [63:0] FP64_POS_INF = 64'h7FF0000000000000;
    localparam [63:0] FP64_NEG_INF = 64'hFFF0000000000000;

    wire               sign_in = gf64_in[63];
    wire [23:0]        exp_in  = gf64_in[62:39];
    wire [38:0]        mant_in = gf64_in[38:0];

    wire is_exp_zero  = (exp_in == 24'd0);
    wire is_exp_max   = (exp_in == EXP_MAX);
    wire is_mant_zero = (mant_in == 39'd0);

    wire cls_zero      = is_exp_zero  &&  is_mant_zero;
    wire cls_subnormal = is_exp_zero  && !is_mant_zero;
    wire cls_inf       = is_exp_max   &&  is_mant_zero;
    wire cls_nan       = is_exp_max   && !is_mant_zero;
    wire cls_normal    = !is_exp_zero && !is_exp_max;

    // Leading-zero-count for subnormal renormalization (39-bit mantissa)
    function integer clz_m;
        input [38:0] v;
        integer i;
        begin
            clz_m = 39;
            for (i = 0; i < 39; i = i + 1)
                if (v[38-i] && (clz_m == 39)) clz_m = i;
        end
    endfunction

    wire signed [31:0] lzc_s = clz_m(mant_in);
    wire signed [47:0] sub_true_exp = ($signed(48'd1) - 48'sd8388607) - (lzc_s + 48'sd1);
    wire [38:0]        sub_frac_bits = (mant_in << (lzc_s[7:0] + 8'd1));
    wire signed [47:0] norm_true_exp = $signed({1'b0, exp_in}) - 48'sd8388607;

    wire signed [47:0] pack_true_exp = cls_subnormal ? sub_true_exp : norm_true_exp;
    wire [38:0]        pack_frac     = cls_subnormal ? sub_frac_bits : mant_in;

    // FP64 normal packer: widen M=39 to FP64_MANT=52 (zero-pad, no rounding)
    wire [51:0] mant52 = {pack_frac, 13'b0};
    wire signed [47:0] norm_exp_final = pack_true_exp + 48'sd1023;
    wire is_fp64_normal = (pack_true_exp >= FP64_MIN_NORM_EXP);
    wire norm_overflow  = is_fp64_normal && (norm_exp_final >= 48'd2047);

    // FP64 subnormal packer
    wire [39:0] full_sig = {1'b1, pack_frac};
    wire signed [47:0] shift_s = 48'sd39 - pack_true_exp + 48'sd1074;
    wire [31:0] shift_clamped = (shift_s < 0) ? 32'd0 : (shift_s > 48'd47 ? 32'd47 : shift_s[31:0]);
    wire [63:0] sub_shifted = (shift_s <= 0) ? (full_sig << (-shift_s)) : (full_sig >> shift_clamped);
    wire [39:0] sub_lost_mask = (shift_clamped == 0) ? 40'd0 : ({40{1'b1}} >> (40 - shift_clamped));
    wire [39:0] sub_lost = full_sig & sub_lost_mask;
    wire        sub_guard = (shift_clamped >= 1) ? sub_lost[shift_clamped-1] : 1'b0;
    wire [39:0] sub_sticky_mask = (shift_clamped >= 1) ? ({40{1'b1}} >> (41 - shift_clamped)) : 40'd0;
    wire        sub_sticky = (shift_clamped >= 1) ? (|(sub_lost & sub_sticky_mask)) : 1'b0;
    wire [53:0] sub_mant_pre = {2'b0, sub_shifted[51:0]};
    wire        sub_round_up = sub_guard && (sub_sticky || sub_shifted[0]);
    wire [53:0] sub_mant_rounded = sub_mant_pre + (sub_round_up ? 54'd1 : 54'd0);
    wire        sub_carry_to_normal = sub_mant_rounded[52];
    wire [51:0] sub_mant52 = sub_mant_rounded[51:0];

    always @(*) begin
        fp64_out = FP64_QNAN;
        is_nan_o = 1'b0; is_inf_o = 1'b0; is_zero_o = 1'b0; is_subnormal_o = 1'b0;
        if (cls_nan) begin
            fp64_out = FP64_QNAN; is_nan_o = 1'b1;
        end else if (cls_inf) begin
            fp64_out = sign_in ? FP64_NEG_INF : FP64_POS_INF; is_inf_o = 1'b1;
        end else if (cls_zero) begin
            fp64_out = {sign_in, 63'b0}; is_zero_o = 1'b1;
        end else if (norm_overflow) begin
            fp64_out = sign_in ? FP64_NEG_INF : FP64_POS_INF; is_inf_o = 1'b1;
        end else if (is_fp64_normal && norm_exp_final >= 1 && norm_exp_final < 2047) begin
            fp64_out = {sign_in, norm_exp_final[10:0], mant52};
        end else begin
            // FP64 subnormal path
            is_subnormal_o = 1'b1;
            if (sub_carry_to_normal)
                fp64_out = {sign_in, 11'd1, 52'b0};
            else if (sub_mant52 == 0)
                fp64_out = {sign_in, 63'b0};
            else
                fp64_out = {sign_in, 11'b0, sub_mant52};
        end
    end
endmodule
`default_nettype none
