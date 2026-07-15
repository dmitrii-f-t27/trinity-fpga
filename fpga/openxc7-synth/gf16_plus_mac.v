`timescale 1ns / 1ps
// ============================================================================
// gf16_plus_mac.v — GF16+ (GoldenFloat16+) Multiply-Accumulate core.
//
// Chains gf_mul_param (GF16 product) -> gf_quire_param (binary64 accumulation).
// "GF16+" = GF16 storage format + wider (binary64) Quire accumulator, so a long
// dot-product accumulates exactly and is rounded to GF16 only on FLUSH.
//
// Operations (in_op):
//   0 MAC     : quire += a * b        (no output produced)
//   1 MACSUB  : quire -= a * b        (no output produced)
//   2 FLUSH   : out_y = round(quire) -> GF16, quire cleared (output produced)
//
// GF16 fixed: E=6, M=9, BIAS=31, HAS_INF=1 (16-bit operand).
// Latency: MUL 1 cycle -> Quire 1 cycle; FLUSH result valid ~4 cycles after kick.
//
// Submodules: gf_mul_param, gf_quire_param (both instantiated as-is).
// ============================================================================
module gf16_plus_mac #(
    parameter EXP_BITS  = 6,
    parameter MANT_BITS = 9,
    parameter TOTAL     = 1 + EXP_BITS + MANT_BITS,   // 16
    parameter BIAS      = (1 << (EXP_BITS - 1)) - 1,  // 31
    parameter HAS_INF   = 1
)(
    input  wire                clk,
    input  wire                rst,
    // AXI-Stream input
    input  wire                in_valid,
    input  wire [1:0]          in_op,      // 0=MAC, 1=MACSUB, 2=FLUSH
    input  wire [TOTAL-1:0]    in_a,
    input  wire [TOTAL-1:0]    in_b,
    output wire                in_ready,
    // AXI-Stream output (valid only on FLUSH)
    output wire                out_valid,
    output wire [TOTAL-1:0]    out_y,
    input  wire                out_ready
);
    // ---- input accept ----
    reg [TOTAL-1:0] a_r, b_r;
    reg [1:0]       op_r;
    reg             kick;        // 1-cycle pulse to start the MUL stage
    reg             busy;        // pipeline occupied

    assign in_ready = !busy;

    // ---- Stage 1: GF16 multiply (a * b -> GF16 product) ----
    wire        mul_ov;
    wire [TOTAL-1:0] mul_y;
    gf_mul_param #(.EXP_BITS(EXP_BITS), .MANT_BITS(MANT_BITS), .HAS_INF(HAS_INF)) u_mul (
        .clk(clk), .rst(rst),
        .in_valid(kick), .in_a(a_r), .in_b(b_r), .in_ready(),
        .out_valid(mul_ov), .out_y(mul_y), .out_ready(1'b1)
    );

    // op aligned with multiply output (1-cycle pipeline register)
    reg [1:0] op_q;
    always @(posedge clk or posedge rst)
        if (rst) op_q <= 2'b10; else if (kick) op_q <= op_r;

    // ---- Stage 2: Quire accumulate / flush ----
    // quire in_b[1:0] op field: 2'b00=ADD, 2'b01=SUB, 2'b10=CLEAR+READ
    reg [1:0] qop_field;
    always @(*) begin
        case (op_q)
            2'd0:    qop_field = 2'b00;  // MAC  -> ADD
            2'd1:    qop_field = 2'b01;  // SUB  -> SUB
            default: qop_field = 2'b10;  // FLUSH-> CLEAR+READ
        endcase
    end
    wire [TOTAL-1:0] q_in_b = {{(TOTAL-2){1'b0}}, qop_field};

    reg             q_kick;
    wire            q_ov;
    wire [TOTAL-1:0] q_y;
    gf_quire_param #(.EXP_BITS(EXP_BITS), .MANT_BITS(MANT_BITS), .HAS_INF(HAS_INF)) u_quire (
        .clk(clk), .rst(rst),
        .in_valid(q_kick), .in_a(mul_y), .in_b(q_in_b), .in_ready(),
        .out_valid(q_ov), .out_y(q_y), .out_ready(1'b1)
    );

    // chain: MUL done -> pulse Quire kick
    always @(posedge clk or posedge rst)
        if (rst) q_kick <= 1'b0; else q_kick <= mul_ov;

    // ---- input / pipeline control ----
    // Pipeline drains one cycle after q_kick (Quire consumed its input).
    wire q_done = q_kick;
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            a_r <= {TOTAL{1'b0}}; b_r <= {TOTAL{1'b0}}; op_r <= 2'b0;
            kick <= 1'b0; busy <= 1'b0;
        end else begin
            kick <= 1'b0;
            if (in_valid && !busy) begin
                a_r  <= in_a; b_r <= in_b; op_r <= in_op;
                kick <= 1'b1; busy <= 1'b1;
            end else if (q_done) begin
                busy <= 1'b0;
            end
        end
    end

    // ---- output register (holds FLUSH result until consumed) ----
    reg [TOTAL-1:0] out_reg;
    reg             ovalid;
    always @(posedge clk or posedge rst) begin
        if (rst) begin out_reg <= {TOTAL{1'b0}}; ovalid <= 1'b0; end
        else begin
            if (ovalid && out_ready) ovalid <= 1'b0;
            if (q_ov) begin out_reg <= q_y; ovalid <= 1'b1; end
        end
    end
    assign out_valid = ovalid;
    assign out_y     = out_reg;
endmodule
