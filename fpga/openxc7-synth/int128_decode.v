// SPDX-License-Identifier: Apache-2.0
// int128_decode.v — signed 128-bit integer → IEEE binary32 (FP32) decode.
// Combinational. RNE rounding. FIX: single always block, 8-bit lzc sentinel=255.
module int128_decode (
    input  wire [127:0] int128_in,
    output reg  [31:0]  fp32_out,
    output wire         is_zero_o,
    output wire         is_inf_o
);
    localparam [31:0] FP32_POS_INF = 32'h7F800000;
    localparam [31:0] FP32_NEG_INF = 32'hFF800000;

    wire sign_in = int128_in[127];
    wire [127:0] abs_val = sign_in ? (~int128_in + 128'd1) : int128_in;
    wire is_zero = (int128_in == 128'd0);
    assign is_zero_o = is_zero;

    // Leading-one detector: 8-bit lzc, sentinel=255 (lzc[7]=1 only for sentinel)
    reg [7:0] lzc;
    integer i;
    always @(*) begin
        lzc = 8'd255; // sentinel
        for (i = 127; i >= 0; i = i - 1) begin
            if (abs_val[i] && lzc[7])
                lzc = i[7:0];
        end
    end

    // Align: shift abs_val left so leading-1 reaches bit 127
    wire [6:0] shl_amt = 7'd127 - lzc[6:0];
    wire [127:0] aligned = abs_val << shl_amt;

    // Extract FP32 components: bit 127=hidden, 126:104=23 mantissa, 103=guard
    wire [22:0] mant23 = aligned[126:104];
    wire        guard  = aligned[103];
    wire        sticky = |aligned[102:0];

    wire round_up = guard && (sticky || mant23[0]);
    wire [23:0] mant_add = {1'b0, mant23} + (round_up ? 24'd1 : 24'd0);
    wire        mant_carry = mant_add[23];

    wire [8:0] exp_biased = {1'b0, lzc[7:0]} + 9'd127 + (mant_carry ? 9'd1 : 9'd0);
    wire overflow = (exp_biased >= 9'd255) && !is_zero;
    assign is_inf_o = overflow;

    always @(*) begin
        if (is_zero)
            fp32_out = 32'h00000000;
        else if (overflow)
            fp32_out = sign_in ? FP32_NEG_INF : FP32_POS_INF;
        else
            fp32_out = {sign_in, exp_biased[7:0], mant_add[22:0]};
    end
endmodule
