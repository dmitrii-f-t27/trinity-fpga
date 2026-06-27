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

    wire                        a_zero = (ea == 0);
    wire                        b_zero = (eb == 0);

    // Implicit leading 1 (MANT_BITS+1 wide)
    wire [MANT_BITS:0] ma_f = {1'b1, ma};
    wire [MANT_BITS:0] mb_f = {1'b1, mb};

    // Larger-magnitude wins
    wire a_larger = (ea > eb) || ((ea == eb) && (ma_f >= mb_f));
    wire [EXP_BITS:0] ediff = a_larger ?
        ({1'b0, ea} - {1'b0, eb}) : ({1'b0, eb} - {1'b0, ea});

    wire [MANT_BITS:0] ma_al = a_larger ? ma_f : (ma_f >> ediff);
    wire [MANT_BITS:0] mb_al = a_larger ? (mb_f >> ediff) : mb_f;
    wire [EXP_BITS-1:0] er   = a_larger ? ea : eb;
    wire                sr   = a_larger ? sa : sb;

    wire               same_sign = (sa == sb);
    wire [MANT_BITS+1:0] sum_add = {1'b0, ma_al} + {1'b0, mb_al};
    wire [MANT_BITS+1:0] sum_sub = {1'b0, ma_al} - {1'b0, mb_al};
    wire [MANT_BITS+1:0] mant_raw = same_sign ? sum_add : sum_sub;

    reg  [TOTAL-1:0]         result_packed;
    reg  [MANT_BITS+1:0]     mw;
    reg  [EXP_BITS:0]        ew;
    reg                       sg;
    integer i;

    always @(*) begin
        if (a_zero)      result_packed = in_b;
        else if (b_zero) result_packed = in_a;
        else begin
            sg = sr; mw = mant_raw; ew = {1'b0, er};
            if (same_sign && mw[MANT_BITS+1]) begin
                mw = mw >> 1; ew = ew + 1;
            end
            if (!same_sign && mw != 0)
                for (i = 0; i < MANT_BITS; i = i + 1)
                    if (!mw[MANT_BITS]) begin
                        mw = mw << 1; ew = ew - 1;
                    end
            if (mw == 0 || ew == 0 || ew[EXP_BITS])
                result_packed = {TOTAL{1'b0}};
            else if (ew > {1'b0, { (EXP_BITS-1){1'b1} }})
                result_packed = {sg, {(EXP_BITS-1){1'b1}}, 1'b0, {MANT_BITS{1'b1}}};
            else
                result_packed = {sg, ew[EXP_BITS-1:0], mw[MANT_BITS-1:0]};
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
