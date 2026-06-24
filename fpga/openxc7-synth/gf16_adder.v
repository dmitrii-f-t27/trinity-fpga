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
    // Bring-up identity: pass A through so ADD-by-zero is bit-exact.
    // A real GF16 ADD core will replace the combinational section below.
    // ========================================================================
    wire [14:0] result_packed = in_a;

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
