//! Strand III: Language \& Hardware Bridge
//!
//! FPGA component for Trinity S³AI — synthesizable Verilog module.
//!

// @origin(spec:gf16_adder.tri) @regen(manual-impl)
// GF16 Adder — Golden Float 16 Addition Unit (AX7203 bring-up variant)
//
// GF16 format (15 bits + sign):
//   [14]    - sign bit (1 = negative)
//   [13:8]  - exponent (6 bits, bias TBD)
//   [7:0]   - mantissa (8 bits, implied hidden bit)
//
// φ² + 1/φ² = 3 | TRINITY
//
// NOTE: This is a **bring-up identity stage** for the AX7203 GF16 UART
// conformance path. It implements a proper AXI-Stream register with
// out_y = in_a, so the ADD identity `a + 0 == a` is bit-exact. The true
// GF16 float ADD core (alignment, hidden-bit add, normalization, rounding)
// will replace this once the UART loop is verified.

`timescale 1ns / 1ps

module gf16_adder (
    // Clock and reset
    input wire        clk,
    input wire        rst,

    // Data input (AXI-Stream compatible handshake)
    input wire        in_valid,
    input wire [14:0] in_a,    // GF16 operand A
    input wire [14:0] in_b,    // GF16 operand B
    output wire        in_ready,

    // Data output
    output wire        out_valid,
    output wire [14:0] out_y,
    input wire        out_ready
);

    // ========================================================================
    // Real GF16 floating-point ADD (15-bit: sign + exp6 + mant8, bias=31)
    // Combinational; replaces the bring-up pass-through. Truncation rounding.
    // ========================================================================
    wire        sa = in_a[14];
    wire [5:0]  ea = in_a[13:8];
    wire [7:0]  ma = in_a[7:0];
    wire        sb = in_b[14];
    wire [5:0]  eb = in_b[13:8];
    wire [7:0]  mb = in_b[7:0];

    wire        a_zero = (ea == 6'd0);
    wire        b_zero = (eb == 6'd0);

    wire [8:0]  ma_f = {1'b1, ma};   // implicit leading 1
    wire [8:0]  mb_f = {1'b1, mb};

    // Larger-magnitude operand wins (by exp, then mantissa)
    wire        a_larger = (ea > eb) || ((ea == eb) && (ma_f >= mb_f));
    wire [6:0]  ediff = a_larger ? ({1'b0,ea} - {1'b0,eb}) : ({1'b0,eb} - {1'b0,ea});

    wire [8:0]  ma_al = a_larger ? ma_f : (ma_f >> ediff);
    wire [8:0]  mb_al = a_larger ? (mb_f >> ediff) : mb_f;
    wire [5:0]  er    = a_larger ? ea : eb;
    wire        sr    = a_larger ? sa : sb;

    wire        same_sign = (sa == sb);
    wire [9:0]  sum_add   = {1'b0, ma_al} + {1'b0, mb_al};
    wire [9:0]  sum_sub   = {1'b0, ma_al} - {1'b0, mb_al};
    wire [9:0]  mant_raw  = same_sign ? sum_add : sum_sub;

    reg  [14:0] result_packed;
    reg  [9:0]  mw;
    reg  [6:0]  ew;
    reg  sg;
    integer i;

    always @(*) begin
        if (a_zero)      result_packed = in_b;
        else if (b_zero) result_packed = in_a;
        else begin
            sg = sr; mw = mant_raw; ew = {1'b0, er};
            // Add overflow: bit 9 set → shift right 1, exp++
            if (same_sign && mw[9]) begin mw = mw >> 1; ew = ew + 1; end
            // Subtraction: normalize (shift left until bit 8 set)
            if (!same_sign && mw != 0)
                for (i = 0; i < 8; i = i + 1)
                    if (!mw[8]) begin mw = mw << 1; ew = ew - 1; end
            // Pack (check underflow/overflow)
            if (mw == 0 || ew == 0 || ew[6])
                result_packed = 15'd0;                        // underflow/zero
            else if (ew > 7'd62)
                result_packed = {sg, 6'd62, 8'hFF};           // saturate
            else
                result_packed = {sg, ew[5:0], mw[7:0]};       // normal
        end
    end

    // ========================================================================
    // Single-stage AXI-Stream output register with proper handshake.
    // ========================================================================
    reg [14:0] out_reg;
    reg        out_valid_reg;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            out_reg       <= 15'b0;
            out_valid_reg <= 1'b0;
        end else begin
            if (out_valid_reg && out_ready) begin
                out_valid_reg <= 1'b0;
            end

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
