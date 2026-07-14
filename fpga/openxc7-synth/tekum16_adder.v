`default_nettype none
`timescale 1ns / 1ps
// =============================================================================
// tekum16_adder.v  (v1 -- structural tapered-precision adder stub)
// -----------------------------------------------------------------------------
// Structural tekum16 floating-point ADD for the Trinity project.
//
// tekum16 = LINEAR tapered precision (S|D|R(3)|characteristic|mantissa),
// working binary-takum-lineage model of arXiv:2512.10964 (Hunhold, Dec 2025),
// interpreted linearly as in conformance/tekum_ref.py. The taper trades
// mantissa width for characteristic width as magnitude moves away from unity:
// near c=0 we have 11 mantissa bits (r_eff=0), at the extremes (|c|>=127) we
// have 4 mantissa bits (r_eff=7).
//
// Field layout (N=16, REGIME_BITS=3, PAYLOAD_BITS=11):
//   bit[15]      = S   (sign)
//   bit[14]      = D   (direction: D=1 -> c>=0, D=0 -> c<0)
//   bit[13:11]   = R   (regime, 3 bits)
//   payload[10:0]= [ C_u (r_eff bits) | M_u (p bits) ]
//       r_eff = D ? R : (7 - R)
//       p     = 11 - r_eff                          (TAPER: mantissa width)
//       c     = CBIAS[{D,R}] + C_u                  (unbiased exponent)
//   value = (-1)^S * (1 + M_u / 2^p) * 2^c
//
//   specials: raw == 0x0000 -> +0 ; raw == 0x8000 -> NaR
//
// DATAPATH:
//   1. Field extraction (S, D, R, payload) for both operands.
//   2. Tapered regime decode: compute r_eff, p, extract variable-width C_u
//      and M_u, look up CBIAS, form signed exponent c.
//   3. Internal normalize: left-justify {1'b1, M_u} into a 12-bit mantissa
//      (implicit bit at position 11) so operands of differing p still align.
//   4. Exponent compare + swap so operand A is the larger magnitude.
//   5. Barrel-shift the smaller operand's mantissa right by |c_a - c_b|
//      (sticky-OR the shifted-out bits for rounding).
//   6. Sign-directed add/subtract of the 12-bit mantissas (with 1 guard bit
//      and a sticky bit -> 14-bit ALU).
//   7. Normalize: find the leading 1 in the 14-bit ALU result, shift it back
//      to position 11, adjust the result exponent accordingly.
//   8. Tapered regime re-encode: given the result exponent, select the unique
//      (D, R) whose CBIAS-interval covers it (the 16 regimes tile [-255,254]
//      without overlap -- see the c-range table below), compute C_u and the
//      right-shift amount for the mantissa (back to p result bits), truncate
//      to p bits (TODO: replace by RNE; truncation matches the gf16_adder.v
//      bring-up rounding policy, NOT the conformance/tekum_ref.py oracle).
//   9. Pack into 16-bit tekum16 and register through an AXI-Stream handshake.
//
// STATUS -- STRUCTURAL STUB:
//   Synthesizable on openXC7 / Artix-7 (no DSP, no carry-chain abuse). The
//   tapered re-encode step (8) uses a priority if-tree over the 16 regimes;
//   this is correct but not LUT-optimal (a leading-one-count + ROM would be
//   smaller). Rounding is TRUNCATION; the golden SW oracle
//   (conformance/tekum_ref.py) does RNE, so this stub is NOT bit-exact with
//   the oracle -- it exists to characterize tapered-add LUT cost and route.
//
//   Sections that MUST be confirmed against the full tekum paper are flagged
//   with  // TODO: verify from full paper  (inherited from tekum_decode_param.v).
//
// Author: Vasilev (gHashTag), ORCID 0009-0008-4294-6159, admin@t27.ai.
// =============================================================================

module tekum16_adder (
    input  wire        clk,
    input  wire        rst,

    // AXI-Stream-style handshake (matches gf16_adder.v convention)
    input  wire        in_valid,
    input  wire [15:0] in_a,      // tekum16 operand A
    input  wire [15:0] in_b,      // tekum16 operand B
    output wire        in_ready,

    output wire        out_valid,
    output wire [15:0] out_y,
    input  wire        out_ready
);

    // ------------------------------------------------------------------
    // static format constants
    // ------------------------------------------------------------------
    localparam integer N            = 16;
    localparam integer REGIME_BITS  = 3;
    localparam integer OVERHEAD     = 2 + REGIME_BITS;       // S + D + R = 5
    localparam integer PAYLOAD_BITS = N - OVERHEAD;          // 11
    localparam integer PMAX         = PAYLOAD_BITS;          // max mantissa width
    localparam [15:0] TEKUM_NAR     = 16'h8000;

    // ==================================================================
    // FIELD EXTRACTION
    // ------------------------------------------------------------------
    // ==================================================================
    wire        Sa = in_a[15];
    wire        Da = in_a[14];
    wire [2:0]  Ra = in_a[13:11];
    wire [PAYLOAD_BITS-1:0] lower_a = in_a[PAYLOAD_BITS-1:0];

    wire        Sb = in_b[15];
    wire        Db = in_b[14];
    wire [2:0]  Rb = in_b[13:11];
    wire [PAYLOAD_BITS-1:0] lower_b = in_b[PAYLOAD_BITS-1:0];

    // specials
    wire a_zero = (in_a == 16'b0);
    wire b_zero = (in_b == 16'b0);
    wire a_nar  = (in_a == TEKUM_NAR);
    wire b_nar  = (in_b == TEKUM_NAR);

    // ==================================================================
    // TAPERED REGIME / p / r_eff  (matches tekum_decode_param.v:115-123)
    // ------------------------------------------------------------------
    // r_eff = D ? R : ((2^REGIME_BITS - 1) - R)
    // p     = PAYLOAD_BITS - r_eff
    // ==================================================================
    wire [2:0] r_comp_a = 3'd7 - Ra;
    wire [2:0] r_eff_a  = Da ? Ra : r_comp_a;
    wire [3:0] p_a      = 4'd11 - {1'b0, r_eff_a};   // 4..11

    wire [2:0] r_comp_b = 3'd7 - Rb;
    wire [2:0] r_eff_b  = Db ? Rb : r_comp_b;
    wire [3:0] p_b      = 4'd11 - {1'b0, r_eff_b};

    // ==================================================================
    // CBIAS lookup  (inherited from takum64_decode.v:22-27; TODO: verify
    // from full tekum paper -- ternary-adapted biases may differ).
    // Index = {D, R} = (D << 3) | R.
    // ==================================================================
    function signed [15:0] cbias_of(input D, input [2:0] R);
        begin
            case ({D, R})
                4'd0:  cbias_of = -16'sd255;
                4'd1:  cbias_of = -16'sd127;
                4'd2:  cbias_of = -16'sd63;
                4'd3:  cbias_of = -16'sd31;
                4'd4:  cbias_of = -16'sd15;
                4'd5:  cbias_of = -16'sd7;
                4'd6:  cbias_of = -16'sd3;
                4'd7:  cbias_of = -16'sd1;
                4'd8:  cbias_of =  16'sd0;
                4'd9:  cbias_of =  16'sd1;
                4'd10: cbias_of =  16'sd3;
                4'd11: cbias_of =  16'sd7;
                4'd12: cbias_of =  16'sd15;
                4'd13: cbias_of =  16'sd31;
                4'd14: cbias_of =  16'sd63;
                4'd15: cbias_of =  16'sd127;
                default: cbias_of = 16'sd0;
            endcase
        end
    endfunction

    wire signed [15:0] cbias_a = cbias_of(Da, Ra);
    wire signed [15:0] cbias_b = cbias_of(Db, Rb);

    // ==================================================================
    // VARIABLE-WIDTH FIELD EXTRACTION  (C_u: r_eff bits, M_u: p bits)
    // ------------------------------------------------------------------
    // payload layout: [ M_u (p bits) | C_u (r_eff bits) ], LSB-first.
    // C_u sits at bit offset p; M_u occupies the low p bits.
    // We extract both into fixed-width containers (zero-extended).
    // ==================================================================
    function [PAYLOAD_BITS-1:0] extract_M_u(input [PAYLOAD_BITS-1:0] pl,
                                            input [3:0] pbits);
        integer i;
        begin
            extract_M_u = {PAYLOAD_BITS{1'b0}};
            for (i = 0; i < PAYLOAD_BITS; i = i + 1)
                if (i < pbits) extract_M_u[i] = pl[i];
        end
    endfunction

    function [7:0] extract_C_u(input [PAYLOAD_BITS-1:0] pl,
                               input [3:0] pbits,
                               input [3:0] reff);
        integer i;
        begin
            extract_C_u = 8'b0;
            for (i = 0; i < PAYLOAD_BITS; i = i + 1)
                if ((i >= pbits) && (i < (pbits + reff)))
                    extract_C_u[i - pbits] = pl[i];
        end
    endfunction

    wire [PAYLOAD_BITS-1:0] M_u_a_w = extract_M_u(lower_a, p_a);
    wire [7:0]              C_u_a   = extract_C_u(lower_a, p_a, {1'b0, r_eff_a});
    wire signed [15:0]      c_a     = cbias_a + $signed({8'b0, C_u_a});

    wire [PAYLOAD_BITS-1:0] M_u_b_w = extract_M_u(lower_b, p_b);
    wire [7:0]              C_u_b   = extract_C_u(lower_b, p_b, {1'b0, r_eff_b});
    wire signed [15:0]      c_b     = cbias_b + $signed({8'b0, C_u_b});

    // ==================================================================
    // INTERNAL NORMALIZE  -- left-justify {1'b1, M_u} into a 12-bit mantissa
    // ------------------------------------------------------------------
    // The mantissa value (1 + M_u / 2^p) is in [1, 2). We place the implicit
    // leading 1 at bit 11 and left-shift M_u by (PAYLOAD_BITS - p) so its
    // MSB sits at bit 10. This gives a uniform 12-bit representation across
    // all regimes, regardless of p.
    // ==================================================================
    wire [11:0] mant_a = {1'b1, (M_u_a_w << (PMAX - p_a))};
    wire [11:0] mant_b = {1'b1, (M_u_b_w << (PMAX - p_b))};

    // ==================================================================
    // EXPONENT COMPARE + SWAP  (operand A becomes the larger magnitude)
    // ------------------------------------------------------------------
    // For ties on exponent, decide by mantissa (both are normalized so this
    // is well-defined). Sign is NOT used in the swap decision -- we carry
    // signs through the ALU and let the add/sub path resolve the result
    // sign from which operand "won".
    // ==================================================================
    wire        a_larger = (c_a > c_b) ||
                           ((c_a == c_b) && (mant_a >= mant_b));

    wire signed [15:0] c_big       = a_larger ? c_a : c_b;
    wire signed [15:0] c_small     = a_larger ? c_b : c_a;
    wire [11:0]        mant_big    = a_larger ? mant_a : mant_b;
    wire [11:0]        mant_small  = a_larger ? mant_b : mant_a;
    wire               s_big       = a_larger ? Sa    : Sb;
    wire               s_small     = a_larger ? Sb    : Sa;

    wire signed [15:0] exp_diff    = c_big - c_small;     // >= 0
    // Clamp: if exp_diff >= 13 the small operand is below the noise floor of
    // the big one (12 mantissa bits + 1 guard); sticky absorbs it.
    wire [4:0]         shift_amt   = (exp_diff > 16'sd13) ? 5'd13
                                                          : exp_diff[4:0];

    // ==================================================================
    // ALIGNMENT SHIFT  -- right-shift mant_small by shift_amt, capture sticky
    // ------------------------------------------------------------------
    // We extend mant_small to 14 bits (12 + 2 spare) so shifts up to 13 stay
    // representable, and OR together all bits that fall off the right into
    // a single sticky bit.
    // ==================================================================
    wire [13:0] mant_small_ext = {2'b0, mant_small};

    reg  [13:0] mant_small_shifted;
    reg         sticky_pre;
    always @(*) begin : align_shift
        integer k;
        mant_small_shifted = mant_small_ext >> shift_amt;
        sticky_pre         = 1'b0;
        for (k = 0; k < 13; k = k + 1)
            if (k < shift_amt)
                sticky_pre = sticky_pre | mant_small_ext[k];
    end

    // ==================================================================
    // ADD / SUBTRACT
    // ------------------------------------------------------------------
    // effective_op = same_sign ? ADD : SUB. We work in 14 bits to absorb the
    // carry-out on add and to keep one guard bit for the normalize stage.
    // ==================================================================
    wire same_sign_eff = (s_big == s_small);
    wire [13:0] big_ext   = {2'b0, mant_big};
    wire [14:0] sum_add   = {1'b0, big_ext} + {1'b0, mant_small_shifted};
    wire [14:0] sum_sub   = {1'b0, big_ext} - {1'b0, mant_small_shifted};
    wire [14:0] sum_raw   = same_sign_eff ? sum_add : sum_sub;
    wire        result_sign = s_big;     // valid for ADD; for SUB needs care
    // For SUB with borrow (sum_sub[14] set), the small operand actually won
    // magnitude-wise (only possible when c_big==c_small and we swapped on a
    // tie-break that didn't capture a sign-flip). Flip sign in that case.
    wire        sub_borrow  = (!same_sign_eff) & sum_sub[14];

    wire [14:0] sum_norm_in = sum_raw;
    wire        sign_final  = result_sign ^ sub_borrow;

    // ==================================================================
    // NORMALIZE  -- shift sum_norm_in so the MSB-most 1 lands at position 11
    // ------------------------------------------------------------------
    // Value invariant. The ALU output sum_norm_in[14:0] holds the integer
    // (mant_big + mant_small_aligned), where each operand was scaled so
    // that its implicit bit sits at position 11 in the original 12-bit
    // mantissa (i.e. value = mant_int / 2^11 * 2^c_big).
    //
    // After the add/sub the MSB-most 1 sits at some position m in [0..14].
    // To re-normalize so the implicit bit is at position 11 in the 12-bit
    // result mantissa, shift by (m - 11) and adjust the exponent by the
    // SAME amount (a right-shift of the integer mantissa corresponds to a
    // LARGER represented exponent, and vice versa):
    //
    //     delta     = m - 11                (signed, range -11..+3)
    //     shift_r   = max(delta, 0)
    //     shift_l   = max(-delta, 0)
    //     c_result  = c_big + delta
    //     mant_result[11:0] = (sum_norm_in shifted by delta)[11:0]
    //
    // For ADD carry-out, m = 12, delta = +1, c_result = c_big + 1, mant
    // shifted right by 1. For SUB shrink, m < 11, delta < 0, c_result
    // decreases, mant shifted left.
    // ==================================================================
    reg  [4:0]  msb_pos;            // position of MSB-most 1 (0..14); 15 = none
    reg         result_zero;
    always @(*) begin : msb_encoder
        integer m;
        msb_pos = 5'd15;                       // sentinel: no 1 found
        for (m = 14; m >= 0; m = m - 1)
            if (sum_norm_in[m] && msb_pos == 5'd15)
                msb_pos = m[4:0];
    end
    always @(*) begin : zero_flag
        result_zero = (msb_pos == 5'd15);
    end

    wire signed [5:0] delta   = $signed({1'b0, msb_pos}) - 6'sd11;
    wire        [4:0] shift_r = (delta > 0) ? delta[4:0] : 5'd0;
    wire        [4:0] shift_l = (delta < 0) ? (-delta[5:0]) : 5'd0;

    // Sign-extend c_big (16-bit signed) to 17 bits, and delta (6-bit signed)
    // to 17 bits, before adding. Concatenation is UNSIGNED in Verilog, so we
    // must explicitly replicate the sign bits.
    wire signed [16:0] c_result = result_zero ? 17'sd0
                                  : ( {c_big[15], c_big}
                                      + {{11{delta[5]}}, delta} );

    // wide-enough intermediate so the left shift never loses the implicit bit
    wire [19:0] sum_shifted_l = {5'b0, sum_norm_in} << shift_l;
    wire [14:0] sum_shifted_r = sum_norm_in >> shift_r;
    wire [14:0] sum_normalized = (shift_l != 5'd0) ? sum_shifted_l[14:0]
                                                   : sum_shifted_r;

    // Extract 12-bit normalized mantissa (implicit bit at 11, fraction at
    // [10:0]). Bits that fell off the bottom on a right-shift are truncated
    // in this stub; sticky_pre is OR'd into the LSB to keep it live.
    // TODO: replace by proper guard+round+sticky RNE rounding.
    wire [11:0] mant_result = sum_normalized[11:0] | {11'b0, sticky_pre};

    // ==================================================================
    // TAPERED REGIME RE-ENCODE
    // ------------------------------------------------------------------
    // Given the result exponent c_result, find the unique (D, R) whose
    // CBIAS-interval covers it. The 16 regimes tile [-255, 254] without
    // overlap, so the mapping is a deterministic function of c_result.
    //
    // c-ranges (cbias, r_eff, p):
    //   c in [-255,-128]: D=0 R=0, cbias=-255, r_eff=7, p=4
    //   c in [-127, -64]: D=0 R=1, cbias=-127, r_eff=6, p=5
    //   c in [ -63, -32]: D=0 R=2, cbias= -63, r_eff=5, p=6
    //   c in [ -31, -16]: D=0 R=3, cbias= -31, r_eff=4, p=7
    //   c in [ -15,  -8]: D=0 R=4, cbias= -15, r_eff=3, p=8
    //   c in [  -7,  -4]: D=0 R=5, cbias=  -7, r_eff=2, p=9
    //   c in [  -3,  -2]: D=0 R=6, cbias=  -3, r_eff=1, p=10
    //   c == -1         : D=0 R=7, cbias=  -1, r_eff=0, p=11
    //   c ==  0         : D=1 R=0, cbias=   0, r_eff=0, p=11
    //   c in [1,2]      : D=1 R=1, cbias=   1, r_eff=1, p=10
    //   c in [3,6]      : D=1 R=2, cbias=   3, r_eff=2, p=9
    //   c in [7,14]     : D=1 R=3, cbias=   7, r_eff=3, p=8
    //   c in [15,30]    : D=1 R=4, cbias=  15, r_eff=4, p=7
    //   c in [31,62]    : D=1 R=5, cbias=  31, r_eff=5, p=6
    //   c in [63,126]   : D=1 R=6, cbias=  63, r_eff=6, p=5
    //   c in [127,254]  : D=1 R=7, cbias= 127, r_eff=7, p=4
    //
    // Out-of-range results saturate: c > 254 -> maxpositive (D=1,R=7, all-1s
    // payload); c < -255 -> +0 (underflow, sign lost per IEEE convention).
    // ==================================================================
    reg         res_D;
    reg  [2:0]  res_R;
    reg  [3:0]  res_r_eff;
    reg  [3:0]  res_p;
    reg  signed [15:0] res_cbias;
    reg         saturate_max;
    reg         underflow;
    always @(*) begin
        // defaults: saturate to max finite (D=1, R=7, all payload bits = 1)
        res_D         = 1'b1;
        res_R         = 3'd7;
        res_r_eff     = 4'd7;
        res_p         = 4'd4;
        res_cbias     = 16'sd127;
        saturate_max  = 1'b0;
        underflow     = 1'b0;

        if (c_result >= 16'sd0) begin
            // positive exponent branch (D=1)
            if (c_result == 16'sd0) begin
                res_D = 1'b1; res_R = 3'd0; res_r_eff = 4'd0; res_p = 4'd11; res_cbias = 16'sd0;
            end else if (c_result <= 16'sd2) begin
                res_D = 1'b1; res_R = 3'd1; res_r_eff = 4'd1; res_p = 4'd10; res_cbias = 16'sd1;
            end else if (c_result <= 16'sd6) begin
                res_D = 1'b1; res_R = 3'd2; res_r_eff = 4'd2; res_p = 4'd9;  res_cbias = 16'sd3;
            end else if (c_result <= 16'sd14) begin
                res_D = 1'b1; res_R = 3'd3; res_r_eff = 4'd3; res_p = 4'd8;  res_cbias = 16'sd7;
            end else if (c_result <= 16'sd30) begin
                res_D = 1'b1; res_R = 3'd4; res_r_eff = 4'd4; res_p = 4'd7;  res_cbias = 16'sd15;
            end else if (c_result <= 16'sd62) begin
                res_D = 1'b1; res_R = 3'd5; res_r_eff = 4'd5; res_p = 4'd6;  res_cbias = 16'sd31;
            end else if (c_result <= 16'sd126) begin
                res_D = 1'b1; res_R = 3'd6; res_r_eff = 4'd6; res_p = 4'd5;  res_cbias = 16'sd63;
            end else if (c_result <= 16'sd254) begin
                res_D = 1'b1; res_R = 3'd7; res_r_eff = 4'd7; res_p = 4'd4;  res_cbias = 16'sd127;
            end else begin
                saturate_max = 1'b1;          // c > 254 -> max finite
            end
        end else begin
            // negative exponent branch (D=0)
            if (c_result >= -16'sd1) begin
                res_D = 1'b0; res_R = 3'd7; res_r_eff = 4'd0; res_p = 4'd11; res_cbias = -16'sd1;
            end else if (c_result >= -16'sd3) begin
                res_D = 1'b0; res_R = 3'd6; res_r_eff = 4'd1; res_p = 4'd10; res_cbias = -16'sd3;
            end else if (c_result >= -16'sd7) begin
                res_D = 1'b0; res_R = 3'd5; res_r_eff = 4'd2; res_p = 4'd9;  res_cbias = -16'sd7;
            end else if (c_result >= -16'sd15) begin
                res_D = 1'b0; res_R = 3'd4; res_r_eff = 4'd3; res_p = 4'd8;  res_cbias = -16'sd15;
            end else if (c_result >= -16'sd31) begin
                res_D = 1'b0; res_R = 3'd3; res_r_eff = 4'd4; res_p = 4'd7;  res_cbias = -16'sd31;
            end else if (c_result >= -16'sd63) begin
                res_D = 1'b0; res_R = 3'd2; res_r_eff = 4'd5; res_p = 4'd6;  res_cbias = -16'sd63;
            end else if (c_result >= -16'sd127) begin
                res_D = 1'b0; res_R = 3'd1; res_r_eff = 4'd6; res_p = 4'd5;  res_cbias = -16'sd127;
            end else if (c_result >= -16'sd255) begin
                res_D = 1'b0; res_R = 3'd0; res_r_eff = 4'd7; res_p = 4'd4;  res_cbias = -16'sd255;
            end else begin
                underflow = 1'b1;              // c < -255 -> +0
            end
        end
    end

    // ==================================================================
    // MANTISSA RE-QUANTIZE  -- truncate the 12-bit normalized mantissa back
    // to the result regime's p bits.
    // ------------------------------------------------------------------
    // mant_result[11] is the implicit bit (always 1 for finite non-zero).
    // The p-bit fraction we keep is mant_result[10 -: p].
    // TODO: replace by RNE (guard/round/sticky already available via
    //       sticky_pre + extra low bits). Truncation matches the bring-up
    //       rounding policy of gf16_adder.v.
    // ==================================================================
    reg [PAYLOAD_BITS-1:0] mant_frac_trunc;
    always @(*) begin
        // Truncation rounding: keep the top `res_p` bits of mant_result[10:0]
        // (the fraction part below the implicit bit). Variable-width right
        // shift synthesizes as a barrel shifter.
        mant_frac_trunc = (mant_result[10:0] >> (4'd11 - res_p));
    end

    // C_u for the result (result exponent - res_cbias). Sign-extend res_cbias
    // (16-bit signed) to match c_result (17-bit signed) before subtracting.
    wire signed [16:0] c_u_signed = c_result - {res_cbias[15], res_cbias};
    wire [7:0]         c_u_result = c_u_signed[7:0];

    // ==================================================================
    // PACK into 16-bit tekum16
    // ------------------------------------------------------------------
    // payload = [ M_u (p bits) | C_u (r_eff bits) ], M_u in low bits
    // ==================================================================
    reg  [PAYLOAD_BITS-1:0] payload_packed;
    always @(*) begin : pack_payload
        integer p;
        payload_packed = {PAYLOAD_BITS{1'b0}};
        // place C_u (low res_r_eff bits of c_u_result) at offset res_p
        for (p = 0; p < PAYLOAD_BITS; p = p + 1) begin
            if (p < res_p)
                payload_packed[p] = mant_frac_trunc[p];
            else if (p < (res_p + res_r_eff))
                payload_packed[p] = c_u_result[p - res_p];
        end
    end

    // ==================================================================
    // SPECIALS + SATURATE + UNDERFLOW dispatch
    // ------------------------------------------------------------------
    // Mirrors gf16_adder.v:80-96 conventions. NaR propagates; zero is the
    // identity; overflow saturates to max finite; underflow flushes to +0.
    // ==================================================================
    wire [15:0] sat_max_raw = {sign_final, 1'b1, 3'd7, {PAYLOAD_BITS{1'b1}}};
    reg  [15:0] result_packed;
    always @(*) begin
        if (a_nar || b_nar)
            result_packed = TEKUM_NAR;
        else if (a_zero && b_zero)
            result_packed = 16'b0;
        else if (a_zero)
            result_packed = in_b;
        else if (b_zero)
            result_packed = in_a;
        else if (result_zero)
            // exact cancellation (e.g. x + (-x)) -- flush to +0
            result_packed = 16'b0;
        else if (saturate_max)
            result_packed = sat_max_raw;
        else if (underflow)
            result_packed = 16'b0;
        else
            result_packed = {sign_final, res_D, res_R, payload_packed};
    end

    // ==================================================================
    // Single-stage AXI-Stream output register (matches gf16_adder.v:100-124)
    // ==================================================================
    reg  [15:0] out_reg;
    reg         out_valid_reg;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            out_reg       <= 16'b0;
            out_valid_reg <= 1'b0;
        end else begin
            if (out_valid_reg && out_ready)
                out_valid_reg <= 1'b0;
            if (in_valid && in_ready) begin
                out_reg       <= result_packed;
                out_valid_reg <= 1'b1;
            end
        end
    end

    assign in_ready  = ~out_valid_reg | out_ready;
    assign out_valid = out_valid_reg;
    assign out_y     = out_reg;

endmodule
`default_nettype wire
