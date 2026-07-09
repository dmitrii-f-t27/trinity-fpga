// gf_wide_decode.v — Simplified GF{N} decode for N>32 (Phase-B formats).
// For N>32, FP32 output only needs 8-bit rebiased exponent + 23-bit mantissa.
// Subnormals flush to zero (valid: for E>8, all GF subnormals are far
// below FP32's minimum subnormal, so they round to zero anyway).
module gf_wide_decode #(
    parameter N = 48,
    parameter E = 18,
    parameter M = 29,
    parameter [E-1:0] BIAS = 0
) (
    input  wire [N-1:0] gf_in,
    output reg  [31:0]  fp32_out
);
    wire          sign        = gf_in[N-1];
    wire [E-1:0]  exp         = gf_in[N-2:M];
    wire [M-1:0]  mant        = gf_in[M-1:0];

    wire          is_emax     = (exp == {E{1'b1}});
    wire          is_zero_exp = (exp == 0);
    wire          is_zero_mant= (mant == 0);

    // Overflow: exp >= BIAS + 128  -> Inf
    // Underflow: exp <= BIAS - 127 -> Zero (or subnormal, flushed for E>8)
    localparam [E:0] OVFL_THRESH = {1'b0, BIAS} + 9'd128;
    localparam [E:0] UDFL_THRESH = (BIAS >= 127) ? ({1'b0, BIAS} - 9'd127) : {E+1{1'b0}};

    wire overflow  = ({1'b0, exp} >= OVFL_THRESH);
    wire underflow = ({1'b0, exp} <= UDFL_THRESH);

    // FP32 exponent = exp - (BIAS - 127) = exp - BIAS + 127
    wire [E:0] fp32_exp_full = {1'b0, exp} - UDFL_THRESH;

    // Mantissa: top 23 bits (constant shift)
    wire [22:0] mant23 = mant >> (M - 23);

    always @* begin
        if (is_emax)
            fp32_out = is_zero_mant ? {sign, 8'hFF, 23'h0} : 32'h7FC00001;
        else if (is_zero_exp)
            fp32_out = {sign, 31'h0};
        else if (overflow)
            fp32_out = {sign, 8'hFF, 23'h0};
        else if (underflow)
            fp32_out = {sign, 31'h0};
        else
            fp32_out = {sign, fp32_exp_full[7:0], mant23};
    end
endmodule
