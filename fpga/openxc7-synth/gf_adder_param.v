`timescale 1ns / 1ps
// Parameterized GoldenFloat ADD — works for GF4 (1S+1E+2M) through GF16 (1S+6E+9M).
// Same algorithm as gf16_adder.v: align exp → effective add/sub → normalize → pack.
// Truncation rounding (no GRS). AXI-Stream handshake identical to gf16_adder.
module gf_adder_param #(
    parameter EXP_BITS  = 6,
    parameter MANT_BITS = 8,
    parameter TOTAL     = 1 + EXP_BITS + MANT_BITS,  // total operand width
    parameter BIAS      = (1 << (EXP_BITS - 1)) - 1
)(
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    in_valid,
    input  wire [TOTAL-1:0]        in_a,
    input  wire [TOTAL-1:0]        in_b,
    output wire                    in_ready,
    output reg                     out_valid,
    output reg  [TOTAL-1:0]        out_y,
    input  wire                    out_ready
);
    // Field extraction
    wire                        sa = in_a[TOTAL-1];
    wire [EXP_BITS-1:0]         ea = in_a[TOTAL-2:MANT_BITS];
    wire [MANT_BITS-1:0]        ma = in_a[MANT_BITS-1:0];
    wire                        sb = in_b[TOTAL-1];
    wire [EXP_BITS-1:0]         eb = in_b[TOTAL-2:MANT_BITS];
    wire [MANT_BITS-1:0]        mb = in_b[MANT_BITS-1:0];

    wire                        a_zero = (in_a == {TOTAL{1'b0}});
    wire                        b_zero = (in_b == {TOTAL{1'b0}});

    // Implicit leading 1 + GRS bits (MANT_BITS+4 wide: 1+MANT_BITS+G+R+S)
    wire [MANT_BITS:0]   ma_f = {1'b1, ma};
    wire [MANT_BITS:0]   mb_f = {1'b1, mb};

    wire a_larger = (ea > eb) || ((ea == eb) && (ma_f >= mb_f));
    wire [EXP_BITS:0] ediff = a_larger ?
        ({1'b0, ea} - {1'b0, eb}) : ({1'b0, eb} - {1'b0, ea});

    // Sticky: OR of all bits below G+R positions (for variable ediff)
    reg sticky_bit;
    integer j;
    always @(*) begin
        sticky_bit = 1'b0;
        for (j = 0; j <= MANT_BITS; j = j + 1)
            if (j < $signed(ediff) - 2)
                sticky_bit = sticky_bit | mb_f[j];
    end

    // Extend to MANT_BITS+4, align, preserve G+R+S
    wire [MANT_BITS+3:0] ma_ext = {ma_f, 3'b000};
    wire [MANT_BITS+3:0] mb_ext = {mb_f, 3'b000};
    wire [MANT_BITS+3:0] ma_al = a_larger ? ma_ext : (ma_ext >> ediff);
    wire [MANT_BITS+3:0] mb_al_raw = a_larger ? (mb_ext >> ediff) : mb_ext;
    // Inject sticky into bit 0
    wire [MANT_BITS+3:0] mb_al = {mb_al_raw[MANT_BITS+3:1], mb_al_raw[0] | sticky_bit};

    wire [EXP_BITS-1:0]  er   = a_larger ? ea : eb;
    wire                 sr   = a_larger ? sa : sb;

    wire                  same_sign = (sa == sb);
    wire [MANT_BITS+4:0]  sum_add = {1'b0, ma_al} + {1'b0, mb_al};
    wire [MANT_BITS+4:0]  sum_sub = {1'b0, ma_al} - {1'b0, mb_al};
    wire [MANT_BITS+4:0]  mant_raw = same_sign ? sum_add : sum_sub;

    reg  [TOTAL-1:0]      result_packed;
    reg  [MANT_BITS+4:0]  mw;
    reg  [EXP_BITS:0]     ew;
    reg                    sg;
    reg                    underflow;
    reg  [MANT_BITS+1:0]  mant_rounded;
    integer i;

    always @(*) begin
        if (a_zero)      result_packed = in_b;
        else if (b_zero) result_packed = in_a;
        else begin
            sg = sr; mw = mant_raw; ew = {1'b0, er}; underflow = 1'b0;
            // Add overflow
            if (same_sign && mw[MANT_BITS+4]) begin
                mw = mw >> 1; ew = ew + 1;
            end
            // Subtraction normalize
            if (!same_sign && mw != 0)
                for (i = 0; i < MANT_BITS+3; i = i + 1)
                    if (!mw[MANT_BITS+3]) begin
                        mw = mw << 1;
                        if (ew == 0) underflow = 1'b1;
                        else ew = ew - 1;
                    end
            // Round-half-to-even using G(bit2) R(bit1) S(bit0)
            // mw layout: [MANT_BITS+3]=implicit1, [MANT_BITS+2:3]=mantissa, [2]=G, [1]=R, [0]=S
            if (mw[2] && (mw[1] || mw[0] || mw[3]))
                mant_rounded = mw[MANT_BITS+3:3] + 1;  // round up
            else
                mant_rounded = mw[MANT_BITS+3:3];       // truncate or ties-even-down
            // Check rounding overflow (mantissa overflowed past implicit 1)
            if (mant_rounded[MANT_BITS+1]) begin
                mant_rounded = mant_rounded >> 1;
                ew = ew + 1;
            end
            // Pack
            if (mw == 0 || underflow)
                result_packed = {TOTAL{1'b0}};
            else if (ew[EXP_BITS])
                result_packed = {sg, {EXP_BITS{1'b1}}, {MANT_BITS{1'b1}}};
            else
                result_packed = {sg, ew[EXP_BITS-1:0], mant_rounded[MANT_BITS-1:0]};
        end
    end

    // AXI-Stream output register
    reg [TOTAL-1:0] out_reg;
    reg             out_valid_reg;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            out_reg       <= {TOTAL{1'b0}};
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
