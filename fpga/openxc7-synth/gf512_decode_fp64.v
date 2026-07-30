// gf512_decode_fp64.v
// -----------------------------------------------------------------------------
// STRICT bit-exact decode of GF512 (N=512, E=195, M=316, BIAS=2^194-1) to IEEE-754
// binary64. RTL witness (#3) for strict SW-bitexact promotion of gf512
// (Trinity Catalog-100 horizon-A). Continuation of gf48/gf96/gf128/gf256.
//
// Widest proven format: M=316 -> 316-52 = 264 mantissa bits rounded RNE on every
// normal decode. BIAS = 2^194-1 (carry as all-ones localparam); working exponent
// signed 201-bit (range +/-2^194).
//
// THEORETICAL-ONLY: GF512 ~401% of XC7A200T (research/COMPLETE_LUT_TABLE.md) —
// the decode law is provably bit-exact (3 witnesses) but the format can NEVER be
// Tier-E (does not fit any current FPGA). Synth/PnR/flash = impossible.
//
// Independent integer datapath from the published 5-class decode law, NO
// reference to gf512_bitexact_oracle.py. iverilog (inv. #6).
//
// Author: Vasilev (gHashTag), ORCID 0009-0008-4294-6159, admin@t27.ai.
// -----------------------------------------------------------------------------
module gf512_decode_fp64 (
    input  wire [511:0] gf_in,
    output reg  [63:0]  fp64_out
);
    localparam integer M    = 316;
    localparam [193:0] BIAS = {194{1'b1}};             // 2^194 - 1  (194 bits all-ones)
    localparam [194:0] EMAX = {195{1'b1}};             // (1<<195)-1
    localparam signed [200:0] BIAS_S = $signed({7'd0, BIAS});

    localparam integer FP64_EBIAS      = 1023;
    localparam integer FP64_MANT       = 52;
    localparam integer FP64_EMAX       = 2047;
    localparam signed [200:0] EXP_OVF   = 1024;
    localparam signed [200:0] EXP_MIN_N = -1022;

    localparam [63:0] QNAN64    = 64'h7FF8000000000001;
    localparam [63:0] POS_INF64 = 64'h7FF0000000000000;
    localparam [63:0] NEG_INF64 = 64'hFFF0000000000000;

    wire         s = gf_in[511];
    wire [194:0] e = gf_in[510:316];
    wire [315:0] m = gf_in[315:0];

    wire is_e_zero = (e == 195'd0);
    wire is_e_max  = (e == EMAX);
    wire is_m_zero = (m == 316'd0);

    // ---- leading-zero count within the 316-bit mantissa (gf512 subnormals) ----
    integer i;
    reg [8:0] lz;              // 0..316
    always @(*) begin
        lz = 9'd316;
        for (i = 0; i < 316; i = i + 1)
            if (m[315-i] && (lz == 9'd316)) lz = i[8:0];
    end

    // ---- normalise: 317-bit full_sig (top = implicit 1) and E2 ---------------
    reg signed [200:0] E2;
    reg [315:0]        frac_field;     // 316-bit fraction below the implicit 1
    always @(*) begin
        if (is_e_zero) begin
            E2         = 201'sd1 - BIAS_S - ($signed({193'd0, lz + 9'd1}));
            frac_field = (m << (lz + 9'd1));
        end else begin
            E2         = $signed({6'd0, e}) - BIAS_S;
            frac_field = m;
        end
    end

    wire [316:0] full_sig = {1'b1, frac_field};    // 317-bit, top set

    // ---- NORMAL-path rounding: drop low 264 of 317 bits -> 53-bit significand
    wire [52:0] keep53_pre = full_sig[316:264];    // 53 bits
    wire        guard_n    = full_sig[263];
    wire        sticky_n   = |full_sig[262:0];
    wire        round_up_n = guard_n && (sticky_n || keep53_pre[0]);
    wire [53:0] keep53_r   = {1'b0, keep53_pre} + (round_up_n ? 54'd1 : 54'd0);
    wire        carry_n    = keep53_r[53];

    // ---- SUBNORMAL/underflow rounding: sh = -E2 + M - 1074 = -E2 - 758 -------
    //      subnormal branch E2 <= -1023 -> sh in [...,317]; E2=-1075 -> sh=317;
    //      sh > 317 (E2 <= -1076) -> flush to 0.
    wire signed [200:0] sh_s   = -E2 - 201'd758;
    wire        sh_le_sb = (sh_s <= 201'd317);
    wire [383:0] fs_w        = {68'd0, full_sig};          // 317 -> 384-bit container
    wire [383:0] sh_u        = sh_s[8:0];                  // only used when sh_le_sb
    wire [383:0] mant_sub_pre = fs_w >> sh_u;
    wire [383:0] drop_mask    = (384'd1 << sh_u) - 384'd1;
    wire [383:0] guard_mask   = (384'd1 << (sh_u - 384'd1));
    wire [383:0] dropped      = fs_w & drop_mask;
    wire        guard_sub    = |(dropped & guard_mask);
    wire [383:0] sticky_mask  = (sh_u >= 384'd2) ? (guard_mask - 384'd1) : 384'd0;
    wire        sticky_sub   = |(dropped & sticky_mask);
    wire        round_up_sub = guard_sub && (sticky_sub || mant_sub_pre[0]);
    wire [383:0] mant_sub_r   = mant_sub_pre + (round_up_sub ? 384'd1 : 384'd0);

    // exp field after a possible normal-path carry (signed sum FIRST, then [10:0]).
    wire signed [200:0] E2_post      = E2 + (carry_n ? 201'sd1 : 201'sd0);
    wire signed [200:0] exp_field_f  = E2_post + 201'sd1023;
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
            else if (mant_sub_r == 384'd0)   fp64_out = {s, 63'd0};
            else if (mant_sub_r[52])         fp64_out = {s, 11'd1, 52'd0};
            else                             fp64_out = {s, 11'd0, mant_sub_r[51:0]};
        end
    end
endmodule
