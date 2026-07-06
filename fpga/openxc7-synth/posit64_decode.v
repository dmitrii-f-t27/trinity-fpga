// SPDX-License-Identifier: Apache-2.0
// posit64_decode — Posit64 (n=64, es=2) → FP32 decode with RNE rounding.
// Posit Standard 2022. useed = 2^(2^2) = 16. value = (-1)^S * 2^(4k + e) * (1+fraction).
// Same algorithm as posit32_decode, wider input (63-bit abs_val, loop-based LZC).
// NaR = 0x8000000000000000.
`default_nettype none
`timescale 1ns / 1ps

module posit64_decode (
    input  wire [63:0] posit_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero,
    output wire        is_nar
);
    assign is_zero = (posit_in == 64'h0000000000000000);
    assign is_nar  = (posit_in == 64'h8000000000000000);

    wire        sign    = posit_in[63];
    wire [62:0] abs_val = sign ? (~posit_in[62:0] + 63'd1) : posit_in[62:0];

    // Regime: regime_sign = abs_val[62]. Count leading identical bits.
    wire        regime_sign = abs_val[62];
    wire [62:0] regime_bits = regime_sign ? ~abs_val : abs_val;

    // Loop-based LZC on 63-bit field (replaces 62-entry casez)
    reg [6:0] lzc;
    integer i;
    always @(*) begin
        lzc = 7'd127; // sentinel
        for (i = 62; i >= 0; i = i - 1) begin
            if (regime_bits[i] && lzc[6])
                lzc = i[6:0];
        end
    end
    // Clamp: max meaningful regime = 61 (63 - sign - terminator)
    wire [6:0] lzc_f = (lzc > 7'd61) ? 7'd61 : lzc;

    wire signed [7:0] regime_k = regime_sign ?
        ($signed({1'b0, lzc_f[6:0]}) - 8'sd1) :
        -$signed({1'b0, lzc_f[6:0]});

    wire [6:0] regime_total = (lzc_f < 7'd61) ? lzc_f + 7'd1 : lzc_f;

    // After regime + terminator: exponent (es=2) + fraction.
    wire [62:0] after_regime = abs_val << regime_total;
    wire [1:0]  e_field       = after_regime[62:61];
    wire [62:0] frac_field    = after_regime << 2;

    // FP32 exponent = 4*k + e + 127 (useed^k = 16^k = 2^(4k))
    wire signed [10:0] four_k  = $signed(regime_k) * 11'sd4;
    wire signed [10:0] exp_raw = four_k + $signed({9'b0, e_field}) + 11'sd127;

    // RNE rounding: fraction up to ~57 bits → extract 23-bit mantissa + guard/round/sticky
    wire [22:0] mant_pre  = frac_field[62:40];
    wire        guard     = frac_field[39];
    wire        round_b   = frac_field[38];
    wire        sticky    = |frac_field[37:0];

    wire        round_up  = guard & (round_b | sticky | mant_pre[0]);
    wire [23:0] mant_rnd  = {1'b0, mant_pre} + (round_up ? 24'd1 : 24'd0);

    wire        mant_carry = mant_rnd[23];
    wire [22:0] mant_final = mant_rnd[22:0];
    wire signed [10:0] exp_final = exp_raw + (mant_carry ? 11'sd1 : 11'sd0);

    always @(*) begin
        if (is_zero)
            fp32_out = 32'h00000000;
        else if (is_nar)
            fp32_out = 32'h7FC00000;  // NaR → qNaN
        else if (exp_final > 11'sd254)
            fp32_out = {sign, 8'hFF, 23'h000000};  // overflow → Inf
        else if (exp_final < 11'sd1)
            fp32_out = {sign, 8'h00, 23'h000000};  // underflow → zero
        else
            fp32_out = {sign, exp_final[7:0], mant_final};
    end

endmodule
`default_nettype wire
