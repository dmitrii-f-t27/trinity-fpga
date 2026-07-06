// SPDX-License-Identifier: Apache-2.0
// int64_decode.v — signed 64-bit integer → IEEE binary32 (FP32) decode.
// Combinational. RNE rounding. Handles zero, ±values, overflow→±Inf.
// Correct: hidden bit NOT in mantissa field; 24-bit adder for rounding carry.
module int64_decode (
    input  wire [63:0] int64_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero_o,
    output wire        is_inf_o
);
    localparam [31:0] FP32_POS_INF = 32'h7F800000;
    localparam [31:0] FP32_NEG_INF = 32'hFF800000;

    wire sign_in = int64_in[63];
    wire [63:0] abs_val = sign_in ? (~int64_in + 64'd1) : int64_in;
    wire is_zero = (int64_in == 64'd0);

    assign is_zero_o = is_zero;

    // Leading-one detector (MSB priority, 7-bit result, sentinel=127 for none)
    reg [6:0] lzc;
    integer i;
    always @(*) begin
        lzc = 7'd127; // sentinel
        for (i = 63; i >= 0; i = i - 1) begin
            if (abs_val[i] && lzc[6]) // lzc[6] set = still sentinel (>=64)
                lzc = i[6:0];
        end
    end

    // Align: shift abs_val left so leading-1 reaches bit 63
    wire [5:0] shl_amt = 6'd63 - {1'b0, lzc[5:0]}; // safe: lzc <= 63 for nonzero
    wire [63:0] aligned = abs_val << shl_amt;

    // Extract FP32 components from aligned:
    // bit 63 = hidden 1 (removed), bits 62:40 = 23 mantissa, bit 39 = guard
    wire [22:0] mant23 = aligned[62:40];
    wire        guard  = aligned[39];
    wire        sticky = |aligned[38:0];

    // RNE: round up if guard=1 AND (sticky OR round_bit OR mantissa LSB)
    wire round_up = guard && (sticky || mant23[0]);

    // 24-bit adder (catches carry from 23-bit mantissa into exponent)
    wire [23:0] mant_add = {1'b0, mant23} + (round_up ? 24'd1 : 24'd0);
    wire        mant_carry = mant_add[23]; // 1 if mantissa overflowed (e.g., 0x7FFFFF+1)

    // Exponent: true_exp = lzc, biased = lzc + 127, +1 if carry
    wire [8:0] exp_biased = {2'b0, lzc} + 9'd127 + (mant_carry ? 9'd1 : 9'd0);
    wire overflow = (exp_biased >= 9'd255) && !is_zero;

    assign is_inf_o = overflow;

    always @(*) begin
        if (is_zero) begin
            fp32_out = 32'h00000000;
        end else if (overflow) begin
            fp32_out = sign_in ? FP32_NEG_INF : FP32_POS_INF;
        end else begin
            fp32_out = {sign_in, exp_biased[7:0], mant_add[22:0]};
        end
    end

endmodule
