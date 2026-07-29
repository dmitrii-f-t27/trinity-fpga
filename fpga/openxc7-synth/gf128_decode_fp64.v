// gf128_decode_fp64.v
// -----------------------------------------------------------------------------
// STRICT bit-exact decode of GF128 (N=128, E=49, M=78, BIAS=281474976710655) to
// IEEE-754 binary64. RTL witness (#3) for the strict SW-bit-exact promotion of
// gf128 (Trinity Catalog-100 horizon-A). Continuation of gf48 / gf96.
//
// Harder than gf96 (M=78 > 59):
//   78 - 52 = 26 mantissa bits must be ROUNDED RNE on every normal decode
//   (gf96 rounded 7, gf48 rounded 0). BIAS = 2^48-1 needs a 48-bit localparam;
//   the working exponent is a signed 56-bit value (range +/-2^48).
//
// Independent integer datapath written from the published 5-class decode law,
// NO reference to gf128_bitexact_oracle.py. Agreement of this RTL with BOTH
// python witnesses (mpmath-exact A and integer B) = 3 independent witnesses.
//
// iverilog (inv. #6: catches fixed-width truncation/OOB that python cannot).
// Synthesis/PnR/flash on AX7203 = [ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ] (64-bit output
// decode candidate, NOT Tier-E).
//
// Author: Vasilev (gHashTag), ORCID 0009-0008-4294-6159, admin@t27.ai.
// -----------------------------------------------------------------------------
module gf128_decode_fp64 (
    input  wire [127:0] gf_in,
    output reg  [63:0]  fp64_out
);
    localparam [47:0] BIAS = 48'hFFFFFFFFFFFF;     // 281474976710655 = 2^48 - 1
    localparam integer M    = 78;
    localparam [48:0] EMAX  = 49'h1FFFFFFFFFFFF;   // (1<<49)-1
    localparam signed [55:0] BIAS_S = 56'd281474976710655;

    // binary64 field constants
    localparam integer FP64_EBIAS      = 1023;
    localparam integer FP64_MANT       = 52;
    localparam integer FP64_EMAX       = 2047;
    localparam signed [55:0] EXP_OVF   = 1024;
    localparam signed [55:0] EXP_MIN_N = -1022;

    localparam [63:0] QNAN64    = 64'h7FF8000000000001;
    localparam [63:0] POS_INF64 = 64'h7FF0000000000000;
    localparam [63:0] NEG_INF64 = 64'hFFF0000000000000;

    wire         s = gf_in[127];
    wire [48:0]  e = gf_in[126:78];
    wire [77:0]  m = gf_in[77:0];

    wire is_e_zero = (e == 49'd0);
    wire is_e_max  = (e == EMAX);
    wire is_m_zero = (m == 78'd0);

    // ---- leading-zero count within the 78-bit mantissa (for gf128 subnormals) -
    integer i;
    reg [6:0] lz;              // 0..78
    always @(*) begin
        lz = 7'd78;
        for (i = 0; i < 78; i = i + 1)
            if (m[77-i] && (lz == 7'd78)) lz = i[6:0];
    end

    // ---- normalise: 79-bit full_sig (top = implicit 1) and E2 ---------------
    reg signed [55:0] E2;
    reg [77:0]        frac_field;     // 78-bit fraction below the implicit 1
    always @(*) begin
        if (is_e_zero) begin
            E2         = 56'sd1 - BIAS_S - ($signed({49'd0, lz + 7'd1}));
            frac_field = (m << (lz + 7'd1));     // implicit-1 shifts out of 78-bit field
        end else begin
            E2         = $signed({7'd0, e}) - BIAS_S;
            frac_field = m;
        end
    end

    wire [78:0] full_sig = {1'b1, frac_field};    // 79-bit, top set

    // ---- NORMAL-path rounding: drop low 26 of 79 bits -> 53-bit significand --
    wire [52:0] keep53_pre = full_sig[78:26];     // 53 bits
    wire        guard_n    = full_sig[25];
    wire        sticky_n   = |full_sig[24:0];
    wire        round_up_n = guard_n && (sticky_n || keep53_pre[0]);
    wire [53:0] keep53_r   = {1'b0, keep53_pre} + (round_up_n ? 54'd1 : 54'd0);
    wire        carry_n    = keep53_r[53];

    // ---- SUBNORMAL/underflow rounding: sh = -E2 + M - 1074 = -E2 - 996 -------
    //      subnormal branch is E2 <= -1023 -> sh in [27,78]; E2=-1075 -> sh=79;
    //      sh > 79 (E2 <= -1076) -> flush to 0.
    wire signed [55:0] sh_s  = -E2 - 56'd996;
    wire        sh_le_sb = (sh_s <= 56'd79);
    // full_sig is 79 bits -> widen to a 96-bit container for the shift datapath.
    wire [95:0] fs_w        = {17'd0, full_sig};
    wire [95:0] sh_u        = sh_s[7:0];                 // 27..79 only used when sh_le_sb
    wire [95:0] mant_sub_pre = fs_w >> sh_u;
    wire [95:0] drop_mask    = (96'd1 << sh_u) - 96'd1;
    wire [95:0] guard_mask   = (96'd1 << (sh_u - 96'd1));
    wire [95:0] dropped      = fs_w & drop_mask;
    wire        guard_sub    = |(dropped & guard_mask);
    wire [95:0] sticky_mask  = (sh_u >= 96'd2) ? (guard_mask - 96'd1) : 96'd0;
    wire        sticky_sub   = |(dropped & sticky_mask);
    wire        round_up_sub = guard_sub && (sticky_sub || mant_sub_pre[0]);
    wire [95:0] mant_sub_r   = mant_sub_pre + (round_up_sub ? 96'd1 : 96'd0);

    // exp field after a possible normal-path carry (signed sum FIRST, then [10:0]).
    wire signed [55:0] E2_post      = E2 + (carry_n ? 56'sd1 : 56'sd0);
    wire signed [55:0] exp_field_f  = E2_post + 56'sd1023;
    wire [10:0]        exp_field_n  = exp_field_f[10:0];

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
            // binary64 subnormal / flush
            if (!sh_le_sb)                   fp64_out = {s, 63'd0};           // underflow
            else if (mant_sub_r == 96'd0)    fp64_out = {s, 63'd0};           // rounded to 0
            else if (mant_sub_r[52])         fp64_out = {s, 11'd1, 52'd0};    // carried to min normal
            else                             fp64_out = {s, 11'd0, mant_sub_r[51:0]};
        end
    end
endmodule
