`default_nettype none
`timescale 1ns / 1ps
// posit128_decode — Posit128 (n=128, es=4) → FP32 decode with RNE rounding.
// Posit Standard 2022. useed = 2^(2^4) = 65536.
// value = (-1)^S * 2^(16k + e) * (1+fraction). NaR = 0x80...0.
module posit128_decode (
    input  wire [127:0] posit_in,
    output reg  [31:0]  fp32_out,
    output wire         is_zero,
    output wire         is_nar
);
    assign is_zero = (posit_in == 128'h0);
    assign is_nar  = (posit_in == {1'b1, 127'b0});

    wire         sign    = posit_in[127];
    wire [126:0] abs_val = sign ? (~posit_in[126:0] + 127'd1) : posit_in[126:0];

    wire         regime_sign = abs_val[126];
    wire [126:0] regime_bits = regime_sign ? ~abs_val : abs_val;

    // LZC via for-loop
    reg [6:0] lzc;
    reg       found;
    integer   i;
    always @(*) begin
        lzc = 7'd0;
        found = 1'b0;
        for (i = 126; i >= 0; i = i - 1) begin
            if (!found) begin
                if (regime_bits[i])
                    found = 1'b1;
                else
                    lzc = lzc + 7'd1;
            end
        end
    end

    wire signed [7:0] regime_k = regime_sign ?
        ($signed({1'b0, lzc}) - 8'sd1) :
        -$signed({1'b0, lzc});

    wire [7:0] regime_total = (lzc < 7'd125) ? lzc + 7'd1 : lzc;

    wire [126:0] after_regime = abs_val << regime_total;
    wire [3:0]   e_field       = after_regime[126:123];
    wire [126:0] frac_field    = after_regime << 4;

    wire signed [15:0] sixteen_k = $signed(regime_k) * 16'sd16;
    wire signed [15:0] exp_raw   = sixteen_k + $signed({12'b0, e_field}) + 16'sd127;

    wire [22:0] mant_pre  = frac_field[126:104];
    wire        guard     = frac_field[103];
    wire        round_b   = frac_field[102];
    wire        sticky    = |frac_field[101:0];

    wire        round_up  = guard & (round_b | sticky | mant_pre[0]);
    wire [23:0] mant_rnd  = {1'b0, mant_pre} + (round_up ? 24'd1 : 24'd0);

    wire        mant_carry = mant_rnd[23];
    wire [22:0] mant_final = mant_rnd[22:0];
    wire signed [15:0] exp_final = exp_raw + (mant_carry ? 16'sd1 : 16'sd0);

    always @(*) begin
        if (is_zero)
            fp32_out = 32'h00000000;
        else if (is_nar)
            fp32_out = 32'h7FC00000;
        else if (exp_final > 16'sd254)
            fp32_out = {sign, 8'hFF, 23'h000000};
        else if (exp_final < 16'sd1)
            fp32_out = {sign, 8'h00, 23'h000000};
        else
            fp32_out = {sign, exp_final[7:0], mant_final};
    end
endmodule
`default_nettype wire
