`default_nettype none
`timescale 1ns / 1ps
// double_double_decode — Bailey/Hida double-double (2x IEEE-754 binary64) -> binary32.
// value = exact sum of hi (dd[63:0]) + lo (dd[127:64]); round RNE to binary32.
// FP-add: unpack -> specials -> align smaller limb -> add/sub -> normalize -> round to 24-bit.
module double_double_decode (input  wire [127:0] dd, output reg [31:0] fp32_out);
    wire [63:0] hi = dd[63:0];
    wire [63:0] lo = dd[127:64];
    wire        sh = hi[63], sl = lo[63];
    wire [10:0] eh = hi[62:52], el = lo[62:52];
    wire [51:0] mh = hi[51:0], ml = lo[51:0];

    wire hi_nan = (eh==11'h7FF) &  |mh;
    wire hi_inf = (eh==11'h7FF) & ~|mh;
    wire lo_nan = (el==11'h7FF) &  |ml;
    wire lo_inf = (el==11'h7FF) & ~|ml;
    wire hi_zero = (eh==0) & ~|mh;
    wire lo_zero = (el==0) & ~|ml;

    // 53-bit significand (implicit 1 for normal, 0 for subnormal) + unbiased exp
    wire [52:0]  mh53 = (eh==0) ? {1'b0, mh} : {1'b1, mh};
    wire [52:0]  ml53 = (el==0) ? {1'b0, ml} : {1'b1, ml};
    wire signed [13:0] eh_u = (eh==0) ? -14'sd1074 : ($signed({3'b0,eh}) - 14'sd1075); // scale: value = mant53 * 2^eh_u
    wire signed [13:0] el_u = (el==0) ? -14'sd1074 : ($signed({3'b0,el}) - 14'sd1075);

    // which limb is larger magnitude?
    wire h_ge_l = (eh_u > el_u) | ((eh_u == el_u) & (mh53 >= ml53));
    // big = larger, small = smaller (mantissa + exp + sign)
    wire [52:0]  bm  = h_ge_l ? mh53 : ml53;
    wire [52:0]  sm  = h_ge_l ? ml53 : mh53;
    wire signed [13:0] be  = h_ge_l ? eh_u : el_u;
    wire signed [13:0] se  = h_ge_l ? el_u : eh_u;
    wire        bs  = h_ge_l ? sh : sl;
    wire        ss  = h_ge_l ? sl : sh;

    // alignment shift of small limb to big exp
    wire signed [13:0] shift = be - se;
    wire shift_huge = (shift > 14'sd60);   // small fully below -> sticky only
    // shift small mant right by `shift`, keep 56 bits + sticky
    // small mant is 53-bit; shift into a 116-bit field to capture sticky, then reduce
    // (use a generous field; sim handles it; synth: the shift is data-dependent, moderate)
    reg [115:0] sm_shf;          // 53-bit mant left-justified at [115:63], room below
    reg sticky_lo;
    always @* begin
        sm_shf = {sm, 63'b0};    // sm at [115:63]
        if (shift >= 14'd0 && shift <= 14'd116) sm_shf = ({sm, 63'b0} >> shift);
        else if (shift > 14'd116) sm_shf = 0;
        sticky_lo = |sm_shf[2:0];          // bits below the round position contribute sticky (coarse)
    end

    // add/sub the big mant (53-bit) and aligned small (top bits at sm_shf[115:63])
    // bring big mant to the same 116-bit grid: bm at [115:63]
    wire [115:0] bm_ext = {bm, 63'b0};
    reg [116:0] sum;            // 1 extra bit for add carry
    reg sum_sign;
    always @* begin
        if (bs == ss) begin
            sum = {1'b0, bm_ext} + {1'b0, sm_shf};
            sum_sign = bs;
        end else begin
            // subtract: big - small (big >= small by magnitude ordering)
            if (bm_ext >= sm_shf) begin sum = {1'b0, bm_ext} - {1'b0, sm_shf}; sum_sign = bs; end
            else begin sum = {1'b0, sm_shf} - {1'b0, bm_ext}; sum_sign = ss; end
        end
    end

    // normalize: find leading 1 in sum[116:0] (sum is ~116-bit), compute binary exponent
    // value = sum * 2^(be - 63)  [since bm_ext was bm<<63 at scale be]
    // find msb of sum
    integer i, msb;
    reg [116:0] s;
    reg signed [14:0] e2;       // binary exponent of the value
    always @* begin
        s = sum;
        msb = -1;
        for (i = 116; i >= 0; i = i-1) if (s[i] && msb == -1) msb = i;
        e2 = (msb < 0) ? 0 : (be + (msb - 63));
    end

    // extract 24-bit FP32 mantissa + guard/round/sticky from sum at `msb`
    // shifted = sum >> (msb-25) so bit msb at pos 25, mant=[25:2], guard=[1], round=[0]
    reg [116:0] shifted;
    reg [24:0] mant25;
    reg guard, rnd, stb, round_up;
    reg [23:0] mant24;
    always @* begin
        if (msb >= 25) shifted = sum >> (msb - 25);
        else           shifted = sum << (25 - msb);
        guard = shifted[1]; rnd = shifted[0];
        stb = (msb >= 9'd26) ? |(sum << (142 - msb)) : 1'b0;   // OR of sum bits below the round point
        mant25 = {1'b0, shifted[25:2]};
        round_up = guard & (rnd | stb | mant25[0]);
        if (round_up) mant25 = mant25 + 1;
        if (mant25[24]) begin mant24 = 24'h800000; e2 = e2 + 1; end
        else mant24 = mant25[23:0];
    end

    always @* begin
        // defaults
        fp32_out = 32'h7FC00000;
        if (hi_nan | lo_nan)                                   fp32_out = 32'h7FC00000;
        else if (hi_inf & lo_inf & (sh != sl))                 fp32_out = 32'h7FC00000;  // inf + (-inf)
        else if (hi_inf)                                       fp32_out = {sh, 8'hFF, 23'h0};
        else if (lo_inf)                                       fp32_out = {sl, 8'hFF, 23'h0};
        else if (hi_zero & lo_zero)                            fp32_out = {(sh & sl) << 31}; // -0 only if both -0
        else begin
            // general finite add (a zero limb has mant=0 -> contributes 0; handled naturally)
            // general finite add
            if (e2 > 15'sd127)      fp32_out = {sum_sign, 8'hFF, 23'h0};
            else if (e2 < -15'sd150) fp32_out = {sum_sign, 31'h0};
            else if (e2 < -15'sd126) begin
                if (e2 >= -15'sd149) fp32_out = {sum_sign, 8'h00, 23'h000001};
                else                  fp32_out = {sum_sign, 31'h0};
            end else
                fp32_out = {sum_sign, e2[7:0] + 8'd127, mant24[22:0]};
        end
        // override: if one limb zero (finite), the general path with that limb's mant=0 + exp=its-scale
        // already produces the correct single-limb-round as long as ordering/align is right.
    end
endmodule
`default_nettype none
