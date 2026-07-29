// gf256_decode_fp64.v
// -----------------------------------------------------------------------------
// STRICT bit-exact decode of GF256 (N=256, E=97, M=158, BIAS=2^96-1) to IEEE-754
// binary64. RTL witness (#3) for the strict SW-bit-exact promotion of gf256
// (Trinity Catalog-100 horizon-A). Continuation of gf48/gf96/gf128.
//
// Widest format so far: M=158 -> 158-52 = 106 mantissa bits rounded RNE on every
// normal decode (gf128 rounded 26). BIAS = 2^96-1 (96-bit localparam); working
// exponent signed 101-bit (range +/-2^96).
//
// Independent integer datapath from the published 5-class decode law, NO
// reference to gf256_bitexact_oracle.py. Agreement with BOTH python witnesses
// (mpmath-exact A + integer B) = 3 independent witnesses.
// iverilog (inv. #6). AX7203 synth/PnR/flash = [ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ].
//
// Author: Vasilev (gHashTag), ORCID 0009-0008-4294-6159, admin@t27.ai.
// -----------------------------------------------------------------------------
module gf256_decode_fp64 (
    input  wire [255:0] gf_in,
    output reg  [63:0]  fp64_out
);
    localparam [95:0]  BIAS = 96'hFFFFFFFFFFFFFFFFFFFFFFFF;   // 2^96 - 1
    localparam integer M    = 158;
    localparam [96:0]  EMAX = 97'h1FFFFFFFFFFFFFFFFFFFFFFFF;  // (1<<97)-1
    localparam signed [100:0] BIAS_S = {5'd0, BIAS};           // 2^96-1 sign-extended

    localparam integer FP64_EBIAS      = 1023;
    localparam integer FP64_MANT       = 52;
    localparam integer FP64_EMAX       = 2047;
    localparam signed [100:0] EXP_OVF   = 1024;
    localparam signed [100:0] EXP_MIN_N = -1022;

    localparam [63:0] QNAN64    = 64'h7FF8000000000001;
    localparam [63:0] POS_INF64 = 64'h7FF0000000000000;
    localparam [63:0] NEG_INF64 = 64'hFFF0000000000000;

    wire         s = gf_in[255];
    wire [96:0]  e = gf_in[254:158];
    wire [157:0] m = gf_in[157:0];

    wire is_e_zero = (e == 97'd0);
    wire is_e_max  = (e == EMAX);
    wire is_m_zero = (m == 158'd0);

    // ---- leading-zero count within the 158-bit mantissa (gf256 subnormals) ---
    integer i;
    reg [7:0] lz;              // 0..158
    always @(*) begin
        lz = 8'd158;
        for (i = 0; i < 158; i = i + 1)
            if (m[157-i] && (lz == 8'd158)) lz = i[7:0];
    end

    // ---- normalise: 159-bit full_sig (top = implicit 1) and E2 ---------------
    reg signed [100:0] E2;
    reg [157:0]        frac_field;     // 158-bit fraction below the implicit 1
    always @(*) begin
        if (is_e_zero) begin
            E2         = 101'sd1 - BIAS_S - ($signed({93'd0, lz + 8'd1}));
            frac_field = (m << (lz + 8'd1));
        end else begin
            E2         = $signed({4'd0, e}) - BIAS_S;
            frac_field = m;
        end
    end

    wire [158:0] full_sig = {1'b1, frac_field};    // 159-bit, top set

    // ---- NORMAL-path rounding: drop low 106 of 159 bits -> 53-bit significand
    wire [52:0] keep53_pre = full_sig[158:106];    // 53 bits
    wire        guard_n    = full_sig[105];
    wire        sticky_n   = |full_sig[104:0];
    wire        round_up_n = guard_n && (sticky_n || keep53_pre[0]);
    wire [53:0] keep53_r   = {1'b0, keep53_pre} + (round_up_n ? 54'd1 : 54'd0);
    wire        carry_n    = keep53_r[53];

    // ---- SUBNORMAL/underflow rounding: sh = -E2 + M - 1074 = -E2 - 916 -------
    //      subnormal branch E2 <= -1023 -> sh in [107,159]; E2=-1075 -> sh=159;
    //      sh > 159 (E2 <= -1076) -> flush to 0.
    wire signed [100:0] sh_s   = -E2 - 101'd916;
    wire        sh_le_sb = (sh_s <= 101'd159);
    wire [191:0] fs_w        = {33'd0, full_sig};          // 159 -> 192-bit container
    wire [191:0] sh_u        = sh_s[7:0];                  // only used when sh_le_sb
    wire [191:0] mant_sub_pre = fs_w >> sh_u;
    wire [191:0] drop_mask    = (192'd1 << sh_u) - 192'd1;
    wire [191:0] guard_mask   = (192'd1 << (sh_u - 192'd1));
    wire [191:0] dropped      = fs_w & drop_mask;
    wire        guard_sub    = |(dropped & guard_mask);
    wire [191:0] sticky_mask  = (sh_u >= 192'd2) ? (guard_mask - 192'd1) : 192'd0;
    wire        sticky_sub   = |(dropped & sticky_mask);
    wire        round_up_sub = guard_sub && (sticky_sub || mant_sub_pre[0]);
    wire [191:0] mant_sub_r   = mant_sub_pre + (round_up_sub ? 192'd1 : 192'd0);

    // exp field after a possible normal-path carry (signed sum FIRST, then [10:0]).
    wire signed [100:0] E2_post      = E2 + (carry_n ? 101'sd1 : 101'sd0);
    wire signed [100:0] exp_field_f  = E2_post + 101'sd1023;
    wire [10:0]         exp_field_n  = exp_field_f[10:0];

    wire is_overflow  = (E2 >= EXP_OVF) || (carry_n && (E2_post >= EXP_OVF));
    wire is_fp64_norm = (E2 >= EXP_MIN_N) && !is_overflow;

    always @(*) begin
        if (is_e_max && !is_m_zero)       fp64_out = QNAN64;
        else if (is_e_max)                fp64_out = s ? NEG_INF64 : POS_INF64;
        else if (is_e_zero && is_m_zero)  fp64_out = {s, 63'd0};
        else if (is_overflow)             fp64_out = s ? NEG_INF64 : POS_INF64;
        else if (is_fp64_norm) begin
            if (carry_n) fp64_out = {s, exp_field_n, 52'd0};
            else         fp64_out = {s, exp_field_n, keep53_r[51:0]};
        end else begin
            if (!sh_le_sb)                   fp64_out = {s, 63'd0};
            else if (mant_sub_r == 192'd0)   fp64_out = {s, 63'd0};
            else if (mant_sub_r[52])         fp64_out = {s, 11'd1, 52'd0};
            else                             fp64_out = {s, 11'd0, mant_sub_r[51:0]};
        end
    end
endmodule
