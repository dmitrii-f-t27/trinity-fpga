// gf96_decode_fp64.v
// -----------------------------------------------------------------------------
// STRICT bit-exact decode of GF96 (N=96, E=36, M=59, BIAS=34359738367) to
// IEEE-754 binary64. This is the RTL witness (#3) for the strict SW-bit-exact
// promotion of gf96 (Trinity Catalog-100 horizon-A).
//
// Why binary64 and why this is HARDER than gf48:
//   gf96 mantissa M=59 > binary64's 52, so 59-52 = 7 mantissa bits must be
//   ROUNDED (round-to-nearest-even) on every normal decode -- unlike gf48
//   (M=29 <= 52) which was a pure left shift with zero rounding.
//   Also gf96's BIAS = 34359738367 (= 2^35-1) overflows a 32-bit Verilog
//   `integer`, so BIAS is carried as a 36-bit localparam and the working
//   exponent true_exp / E2 as a 41-bit signed value (range +/-2^35).
//
// Range vs binary64:
//   gf96 true_exp spans +/-2^35 (~3.4e10) vs binary64's +/-1023/1074. Hence
//   codes with |true_exp| > ~1074 map to +/-inf (overflow) or +/-0 (underflow)
//   in binary64; only the e ~= BIAS window produces finite nonzero output, and
//   that is the only place the 59->52 rounding can actually bite.
//
// Independent implementation: integer datapath written from the published
// 5-class decode law with NO reference to gf96_bitexact_oracle.py. Agreement
// of this RTL with BOTH python witnesses (mpmath-exact A and integer B) over
// the representative+boundary+random sweep = 3 independent witnesses.
//
// Simulated with iverilog (inv. #6: python arbitrary-width transcription does
// NOT catch fixed-width Verilog truncation/OOB bugs). Synthesis/PnR/flash on
// AX7203 = [ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ] (64-bit-output decode candidate,
// separate epic from the FP32 lineup -- NOT Tier-E).
//
// Author: Vasilev (gHashTag), ORCID 0009-0008-4294-6159, admin@t27.ai.
// -----------------------------------------------------------------------------
module gf96_decode_fp64 (
    input  wire [95:0] gf_in,
    output reg  [63:0] fp64_out
);
    localparam [35:0] BIAS = 36'h7FFFFFFFF;      // 34359738367 = 2^35 - 1
    localparam integer M    = 59;
    localparam [35:0] EMAX  = 36'hFFFFFFFFF;     // (1<<36)-1
    localparam signed [40:0] BIAS_S = 41'd34359738367;

    // binary64 field constants
    localparam integer FP64_EBIAS      = 1023;
    localparam integer FP64_MANT       = 52;
    localparam integer FP64_EMAX       = 2047;   // exp field of inf/nan
    localparam signed [40:0] EXP_OVF   = 1024;   // E2 >= 1024  -> overflow
    localparam signed [40:0] EXP_MIN_N = -1022;  // smallest E2 for binary64 normal
    localparam signed [40:0] EXP_UF_LO = -1075;  // E2 <= -1075 with sh>60 -> flush to 0

    localparam [63:0] QNAN64    = 64'h7FF8000000000001;
    localparam [63:0] POS_INF64 = 64'h7FF0000000000000;
    localparam [63:0] NEG_INF64 = 64'hFFF0000000000000;

    wire        s = gf_in[95];
    wire [35:0] e = gf_in[94:59];
    wire [58:0] m = gf_in[58:0];

    wire is_e_zero = (e == 36'd0);
    wire is_e_max  = (e == EMAX);
    wire is_m_zero = (m == 59'd0);

    // ---- leading-zero count within the 59-bit mantissa (for gf96 subnormals) -
    integer i;
    reg [5:0] lz;              // 0..59
    always @(*) begin
        lz = 6'd59;
        for (i = 0; i < 59; i = i + 1)
            if (m[58-i] && (lz == 6'd59)) lz = i[5:0];
    end

    // ---- normalise: produce 60-bit full_sig (top bit = implicit 1) and E2 ----
    // value = full_sig * 2^(E2 - M), significand in [1,2), E2 = floor(log2).
    reg signed [40:0] E2;
    reg [58:0]        frac_field;     // 59-bit fraction below the implicit 1
    always @(*) begin
        if (is_e_zero) begin
            // subnormal: value = (m/2^M)*2^(1-BIAS); renormalise within the field.
            E2         = 41'sd1 - BIAS_S - ($signed({35'd0, lz + 6'd1}));
            frac_field = (m << (lz + 6'd1));     // implicit-1 shifts out of 59-bit field
        end else begin
            E2         = $signed({5'd0, e}) - BIAS_S;
            frac_field = m;
        end
    end

    wire [59:0] full_sig = {1'b1, frac_field};    // 60-bit, top set

    // ---- NORMAL-path rounding: drop low 7 of 60 bits -> 53-bit significand --
    wire [52:0] keep53_pre = full_sig[59:7];      // 53 bits
    wire        guard_n    = full_sig[6];
    wire        sticky_n   = |full_sig[5:0];
    wire        round_up_n = guard_n && (sticky_n || keep53_pre[0]);
    wire [53:0] keep53_r   = {1'b0, keep53_pre} + (round_up_n ? 54'd1 : 54'd0);
    wire        carry_n    = keep53_r[53];        // rounded up to 2^53 -> next binade

    // ---- SUBNORMAL/underflow-path rounding: sh = -E2 - 1015 (units of 2^-1074)
    //      only meaningful when E2 in [-1075,-1023]; sh in [8,60]; sh>60 -> flush.
    wire signed [40:0] sh_s = -E2 - 41'd1015;      // >= 8 in the subnormal branch
    wire        sh_le60 = (sh_s <= 41'd60);        // else flush to zero
    // compute in 64 bits to avoid width surprises at large sh
    wire [63:0] fs64        = {4'd0, full_sig};
    wire [63:0] sh_u        = sh_s[7:0];           // 8..60 only used when sh_le60
    wire [63:0] mant_sub_pre = fs64 >> sh_u;
    wire [63:0] drop_mask    = (64'd1 << sh_u) - 64'd1;        // bits [0..sh-1]
    wire [63:0] guard_mask   = (64'd1 << (sh_u - 64'd1));       // bit sh-1
    wire [63:0] dropped      = fs64 & drop_mask;
    wire        guard_sub    = |(dropped & guard_mask);
    wire [63:0] sticky_mask  = (sh_u >= 64'd2) ? ((guard_mask - 64'd1)) : 64'd0;
    wire        sticky_sub   = |(dropped & sticky_mask);
    wire        round_up_sub = guard_sub && (sticky_sub || mant_sub_pre[0]);
    wire [63:0] mant_sub_r   = mant_sub_pre + (round_up_sub ? 64'd1 : 64'd0);

    // exp field after a possible normal-path carry. Computed as a SIGNED sum
    // (E2_post + 1023): slicing [10:0] off a two's-complement negative E2 would
    // yield garbage, so the signed add must happen first, then take the low 11.
    wire signed [40:0] E2_post      = E2 + (carry_n ? 41'sd1 : 41'sd0);
    wire signed [40:0] exp_field_f  = E2_post + 41'sd1023;
    wire [10:0]        exp_field_n  = exp_field_f[10:0];

    // class selection --------------------------------------------------------
    // overflow: E2 already >= 1024, OR a normal-path carry pushed E2 to 1024.
    // (the redundant `exp_field >= 2047` test is intentionally absent: for
    //  negative E2 it would false-trigger off the low-11-bit slice.)
    wire is_overflow  = (E2 >= EXP_OVF) || (carry_n && (E2_post >= EXP_OVF));
    wire is_fp64_norm = (E2 >= EXP_MIN_N) && !is_overflow;

    always @(*) begin
        if (is_e_max && !is_m_zero)       fp64_out = QNAN64;
        else if (is_e_max)                fp64_out = s ? NEG_INF64 : POS_INF64;
        else if (is_e_zero && is_m_zero)  fp64_out = {s, 63'd0};
        else if (is_overflow)             fp64_out = s ? NEG_INF64 : POS_INF64;
        else if (is_fp64_norm) begin
            // carry_n folded: if carried, significand = 2^52 (mant52=0), exp+1
            if (carry_n) fp64_out = {s, exp_field_n, 52'd0};
            else         fp64_out = {s, exp_field_n, keep53_r[51:0]};
        end else begin
            // binary64 subnormal / flush
            if (!sh_le60)                    fp64_out = {s, 63'd0};          // underflow
            else if (mant_sub_r == 64'd0)    fp64_out = {s, 63'd0};          // rounded to 0
            else if (mant_sub_r[52])         fp64_out = {s, 11'd1, 52'd0};   // carried to min normal
            else                             fp64_out = {s, 11'd0, mant_sub_r[51:0]};
        end
    end
endmodule
