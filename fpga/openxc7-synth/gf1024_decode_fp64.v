// gf1024_decode_fp64.v
// -----------------------------------------------------------------------------
// STRICT bit-exact decode of GF1024 (N=1024, E=391, M=632, BIAS=2^390-1) to
// IEEE-754 binary64. RTL witness (#3) for strict SW-bitexact promotion of gf1024
// (Trinity Catalog-100 horizon-A closure). Final format of the gf48..gf1024 line.
//
// M=632 -> 632-52 = 580 mantissa bits rounded RNE per normal decode. BIAS = 2^390-1
// (390-bit all-ones localparam); working exponent signed 401-bit (range +/-2^390).
//
// THEORETICAL-ONLY: GF1024 ~1605% of XC7A200T (research/COMPLETE_LUT_TABLE.md) —
// decode law provably bit-exact (3 witnesses) but can NEVER be Tier-E (~16x too
// big for any current FPGA). Synth/PnR/flash = impossible.
//
// Independent integer datapath from the published 5-class decode law. iverilog.
//
// Author: Vasilev (gHashTag), ORCID 0009-0008-4294-6159, admin@t27.ai.
// -----------------------------------------------------------------------------
module gf1024_decode_fp64 (
    input  wire [1023:0] gf_in,
    output reg  [63:0]   fp64_out
);
    localparam integer M     = 632;
    localparam [389:0] BIAS  = {390{1'b1}};             // 2^390 - 1  (390 bits all-ones)
    localparam [390:0] EMAX  = {391{1'b1}};             // (1<<391)-1
    localparam signed [400:0] BIAS_S = $signed({11'd0, BIAS});

    localparam integer FP64_EBIAS      = 1023;
    localparam integer FP64_MANT       = 52;
    localparam integer FP64_EMAX       = 2047;
    localparam signed [400:0] EXP_OVF   = 1024;
    localparam signed [400:0] EXP_MIN_N = -1022;

    localparam [63:0] QNAN64    = 64'h7FF8000000000001;
    localparam [63:0] POS_INF64 = 64'h7FF0000000000000;
    localparam [63:0] NEG_INF64 = 64'hFFF0000000000000;

    wire         s = gf_in[1023];
    wire [390:0] e = gf_in[1022:632];
    wire [631:0] m = gf_in[631:0];

    wire is_e_zero = (e == 391'd0);
    wire is_e_max  = (e == EMAX);
    wire is_m_zero = (m == 632'd0);

    // ---- leading-zero count within the 632-bit mantissa (gf1024 subnormals) ---
    integer i;
    reg [9:0] lz;              // 0..632
    always @(*) begin
        lz = 10'd632;
        for (i = 0; i < 632; i = i + 1)
            if (m[631-i] && (lz == 10'd632)) lz = i[9:0];
    end

    // ---- normalise: 633-bit full_sig (top = implicit 1) and E2 ---------------
    reg signed [400:0] E2;
    reg [631:0]        frac_field;     // 632-bit fraction below the implicit 1
    always @(*) begin
        if (is_e_zero) begin
            E2         = 401'sd1 - BIAS_S - ($signed({389'd0, lz + 10'd1}));
            frac_field = (m << (lz + 10'd1));
        end else begin
            E2         = $signed({10'd0, e}) - BIAS_S;
            frac_field = m;
        end
    end

    wire [632:0] full_sig = {1'b1, frac_field};    // 633-bit, top set

    // ---- NORMAL-path rounding: drop low 580 of 633 bits -> 53-bit significand
    wire [52:0] keep53_pre = full_sig[632:580];    // 53 bits
    wire        guard_n    = full_sig[579];
    wire        sticky_n   = |full_sig[578:0];
    wire        round_up_n = guard_n && (sticky_n || keep53_pre[0]);
    wire [53:0] keep53_r   = {1'b0, keep53_pre} + (round_up_n ? 54'd1 : 54'd0);
    wire        carry_n    = keep53_r[53];

    // ---- SUBNORMAL/underflow rounding: sh = -E2 + M - 1074 = -E2 - 442 -------
    //      subnormal branch E2 <= -1023 -> sh in [...,633]; E2=-1075 -> sh=633;
    //      sh > 633 (E2 <= -1076) -> flush to 0.
    wire signed [400:0] sh_s   = -E2 - 401'd442;
    wire        sh_le_sb = (sh_s <= 401'd633);
    wire [767:0] fs_w        = {135'd0, full_sig};         // 633 -> 768-bit container
    wire [767:0] sh_u        = sh_s[9:0];                  // only used when sh_le_sb
    wire [767:0] mant_sub_pre = fs_w >> sh_u;
    wire [767:0] drop_mask    = (768'd1 << sh_u) - 768'd1;
    wire [767:0] guard_mask   = (768'd1 << (sh_u - 768'd1));
    wire [767:0] dropped      = fs_w & drop_mask;
    wire        guard_sub    = |(dropped & guard_mask);
    wire [767:0] sticky_mask  = (sh_u >= 768'd2) ? (guard_mask - 768'd1) : 768'd0;
    wire        sticky_sub   = |(dropped & sticky_mask);
    wire        round_up_sub = guard_sub && (sticky_sub || mant_sub_pre[0]);
    wire [767:0] mant_sub_r   = mant_sub_pre + (round_up_sub ? 768'd1 : 768'd0);

    // exp field after a possible normal-path carry (signed sum FIRST, then [10:0]).
    wire signed [400:0] E2_post      = E2 + (carry_n ? 401'sd1 : 401'sd0);
    wire signed [400:0] exp_field_f  = E2_post + 401'sd1023;
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
            else if (mant_sub_r == 768'd0)   fp64_out = {s, 63'd0};
            else if (mant_sub_r[52])         fp64_out = {s, 11'd1, 52'd0};
            else                             fp64_out = {s, 11'd0, mant_sub_r[51:0]};
        end
    end
endmodule
