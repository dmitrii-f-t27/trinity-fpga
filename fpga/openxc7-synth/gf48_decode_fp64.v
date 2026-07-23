// gf48_decode_fp64.v
// -----------------------------------------------------------------------------
// STRICT bit-exact decode of GF48 (N=48, E=18, M=29, BIAS=131071) to IEEE-754
// binary64. Unlike gf_decode_param.v (which targets binary32 and therefore
// TRUNCATES gf48's 29-bit mantissa to 23 bits -> only self-consistent), this
// module widens into binary64 (52 mantissa bits >= 29) so every finite gf48
// normal value maps with ZERO rounding. This is the RTL witness (#3) for the
// strict SW-bit-exact promotion of gf48 (Trinity Catalog-100 horizon-A).
//
// It is an INDEPENDENT implementation from gf48_bitexact_oracle.py: integer
// datapath, no reference to the Python code, mirroring only the published
// 5-class decode law. Agreement of this RTL with BOTH python witnesses over
// the representative+boundary+random sweep = 3 independent witnesses.
//
// Simulated with iverilog (independent witness requirement, inv. #6: python
// arbitrary-width transcription does NOT catch fixed-width Verilog bugs).
// Synthesis/PnR/flash on AX7203 = [ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ] (this is a
// 64-bit-output decode-HW candidate, separate epic from the FP32 lineup).
//
// Author: Vasilev (gHashTag), ORCID 0009-0008-4294-6159, admin@t27.ai.
// -----------------------------------------------------------------------------
module gf48_decode_fp64 (
    input  wire [47:0] gf_in,
    output reg  [63:0] fp64_out
);
    localparam integer N = 48, E = 18, M = 29, BIAS = 131071;
    localparam [17:0] EMAX = 18'h3FFFF;         // (1<<18)-1
    localparam integer FP64_EBIAS = 1023;
    localparam integer FP64_MANT  = 52;
    localparam integer FP64_EMAX  = 2047;
    localparam integer FP64_MIN_NORM_EXP = -1022;
    localparam integer FP64_SUB_LSB_EXP  = -1074;
    localparam [63:0] QNAN64    = 64'h7FF8000000000001;
    localparam [63:0] POS_INF64 = 64'h7FF0000000000000;
    localparam [63:0] NEG_INF64 = 64'hFFF0000000000000;

    wire        s = gf_in[47];
    wire [17:0] e = gf_in[46:29];
    wire [28:0] m = gf_in[28:0];

    wire is_e_zero = (e == 18'd0);
    wire is_e_max  = (e == EMAX);
    wire is_m_zero = (m == 29'd0);

    // ---- leading-zero count within the 29-bit mantissa (for subnormals) ----
    integer i;
    reg [5:0] lz;              // 0..29
    always @(*) begin
        lz = 6'd29;
        for (i = 0; i < 29; i = i + 1)
            if (m[28-i] && (lz == 6'd29)) lz = i[5:0];
    end

    // signed working exponent (wide enough for BIAS up to 131071)
    reg signed [31:0] true_exp;
    reg [28:0]        frac_field;   // 29-bit fraction after the implicit 1
    always @(*) begin
        if (is_e_zero) begin
            // subnormal: value = (m/2^M)*2^(1-BIAS); renormalise
            true_exp   = (1 - BIAS) - (lz + 1);
            frac_field = (m << (lz + 1));   // top bit (implicit 1) shifts out of 29-bit field
        end else begin
            true_exp   = $signed({14'd0, e}) - BIAS;
            frac_field = m;
        end
    end

    // widen 29-bit fraction to 52-bit binary64 fraction (pure left shift, exact)
    wire [51:0] mant52_norm = {23'd0, frac_field} << (FP64_MANT - M); // M=29 => <<23

    // subnormal-of-fp64 path (gradual underflow) -- gf48 min true_exp ~ -131070,
    // far below fp64 min normal -1022, so tiny gf48 values become fp64 subnormals
    // or flush. full_sig = 1.frac (M+1 = 30 bits).
    wire [29:0] full_sig = {1'b1, frac_field};
    // value = full_sig * 2^(true_exp - M). As multiple of 2^-1074:
    //   shift = M - true_exp + FP64_SUB_LSB_EXP
    wire signed [31:0] shift_s = M - true_exp + FP64_SUB_LSB_EXP;
    // clamp
    localparam integer MAXSH = 30 + 8;
    wire [31:0] shsat = (shift_s < 0) ? 32'd0 :
                        (shift_s > MAXSH) ? MAXSH[31:0] : shift_s[31:0];
    wire [63:0] fs64 = {34'd0, full_sig};
    wire [63:0] sub_shifted = (shift_s <= 0) ? (fs64 << (-shift_s)) : (fs64 >> shsat);
    wire [63:0] lost_mask = (shsat == 0) ? 64'd0 : (~64'd0 >> (64 - shsat));
    wire [63:0] lost      = fs64 & lost_mask;
    wire        guard_b   = (shsat >= 1) ? lost[shsat-1] : 1'b0;
    wire [63:0] sticky_mask = (shsat >= 2) ? (~64'd0 >> (64 - (shsat-1))) : 64'd0;
    wire        sticky_b  = (shsat >= 2) ? (|(lost & sticky_mask)) : 1'b0;
    wire [52:0] sub_mant_pre = sub_shifted[52:0];
    wire        sub_round_up = guard_b && (sticky_b || sub_shifted[0]);
    wire [52:0] sub_mant_r   = sub_mant_pre + (sub_round_up ? 53'd1 : 53'd0);

    wire signed [31:0] exp_field = true_exp + FP64_EBIAS;
    wire is_fp64_normal = (true_exp >= FP64_MIN_NORM_EXP);

    always @(*) begin
        if (is_e_max && !is_m_zero)        fp64_out = QNAN64;
        else if (is_e_max)                 fp64_out = s ? NEG_INF64 : POS_INF64;
        else if (is_e_zero && is_m_zero)   fp64_out = {s, 63'd0};
        else if (is_fp64_normal) begin
            if (exp_field >= FP64_EMAX)    fp64_out = s ? NEG_INF64 : POS_INF64;
            else fp64_out = {s, exp_field[10:0], mant52_norm};
        end else begin
            // fp64 subnormal / flush
            if (sub_mant_r == 53'd0)       fp64_out = {s, 63'd0};
            else if (sub_mant_r[52])       fp64_out = {s, 11'd1, 52'd0}; // carried to min normal
            else                           fp64_out = {s, 11'd0, sub_mant_r[51:0]};
        end
    end
endmodule
