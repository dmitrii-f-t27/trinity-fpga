`default_nettype none
`timescale 1ns / 1ps
// =============================================================================
// tekum_decode_param.v  (v1 -- structural stub)
// -----------------------------------------------------------------------------
// Parametric decode module for the tekum family (Trinity project):
//   tekum8, tekum16, tekum32
//
// Tekum = balanced-ternary TAPERED precision real arithmetic
// (arXiv:2512.10964, Hunhold, Dec 2025). It is the ternary successor of takum
// (arXiv:2404.18603) and shares tapered-precision lineage with posit/takum:
// the mantissa WIDTH varies with magnitude -- more bits near unity, fewer at
// the extremes -- via a variable-length regime/characteristic field.
//
// STATUS -- STRUCTURAL STUB:
//   The exact trit-level tekum encoding requires verification against the full
//   23-page paper (the arXiv abstract alone does not specify the per-regime
//   bias tables or the balanced-ternary scaling law, and the PDF/HTML are not
//   machine-readable here). The FIELD LAYOUT below follows the takum decoder
//   already in this repository (fpga/openxc7-synth/takum64_decode.v, the
//   binary parent format), interpreted LINEARLY (sign + exponent + mantissa)
//   rather than logarithmically, to match the exact-Fraction golden oracle in
//   conformance/tekum_ref.py. Sections that MUST be confirmed against the full
//   paper are flagged with  // TODO: verify from full paper
//
// Field layout (working hypothesis, mirrors tekum_ref.py / takum lineage):
//   bit[N-1]       = S  (sign)
//   bit[N-2]       = D  (direction)
//   bit[N-3 : N-5] = R  (regime, REGIME_BITS=3 wide)        overhead = 5 bits
//   payload (N-5)  = [ characteristic C_u : r_eff bits ][ mantissa M_u : p bits ]
//       r_eff = D ? R : ((2^REGIME_BITS - 1) - R)
//       p     = pmax - r_eff        (pmax = N - 5)          // the TAPER
//       c     = CBIAS[{D,R}] + C_u  (unbiased exponent)
//   value = (-1)^S * (1 + M_u / 2^p) * 2^c   (finite, normalized)
//
//   specials: raw == 0 -> +0 ; raw == (1<<(N-1)) -> NaR (Not a Real)
//
// Decode produces an INTERNAL representation (sign, unbiased exponent, mantissa
// with the implicit leading bit pre-pended) suitable for feeding a downstream
// FP32/binary64 packer. An optional combinational FP32 pack path mirrors the
// approach in gf_decode_param.v and is left as TODO for the tapered edge cases.
//
// This file is sandbox design output. Correctness is asserted structurally and
// against conformance/tekum_ref.py (Python golden Fraction oracle) via the
// self-test there; openXC7 synthesis/PnR on AX7203 = [requires user action].
//
// Author: Vasilev (gHashTag), ORCID 0009-0008-4294-6159, admin@t27.ai.
// =============================================================================

module tekum_decode_param #(
    parameter integer N           = 16,     // total tekum width
    parameter integer REGIME_BITS = 3,      // regime field width (takum lineage)
    parameter integer OUT_REG     = 0       // 0 = combinational, 1 = registered
) (
    input  wire                 clk,        // used only when OUT_REG=1
    input  wire                 rst_n,      // sync active-low reset, OUT_REG=1 only
    input  wire [N-1:0]         tekum_in,   // raw tekum{N} encoded word

    // --- internal decoded representation (sign, unbiased exp, mantissa w/ implicit) ---
    output wire                 sign_o,
    output wire signed [31:0]   exp_o,      // unbiased exponent c (signed)
    output wire [N-1:0]         mant_o,     // mantissa with implicit leading 1 in MSB
    output wire [7:0]           mant_msb_idx_o, // position of implicit bit within mant_o

    // --- classification ---
    output wire                 is_nar_o,   // Not a Real (sign-bit-only pattern)
    output wire                 is_zero_o,
    output wire                 is_finite_o,

    // --- optional FP32 view (combinational; TODO tapered edge cases) ---
    output wire [31:0]          fp32_out
);
    // -------------------------------------------------------------------
    // Static elaboration-time checks
    // -------------------------------------------------------------------
    // synthesis translate_off
    initial begin
        if (N < 6) begin
            $display("ERROR tekum_decode_param: N=%0d too small (need >= 6 for S+D+R+payload)", N);
            $finish;
        end
    end
    // synthesis translate_on

    localparam integer OVERHEAD     = 2 + REGIME_BITS;          // S + D + R
    localparam integer PAYLOAD_BITS = N - OVERHEAD;             // = pmax
    localparam integer REGIME_COUNT = (1 << REGIME_BITS);       // 8

    // ---- field extraction ----
    wire                 S = tekum_in[N-1];
    wire                 D = tekum_in[N-2];
    wire [REGIME_BITS-1:0] R = tekum_in[N-3 -: REGIME_BITS];   // bits [N-3 : N-5]
    wire [PAYLOAD_BITS-1:0] lower = tekum_in[PAYLOAD_BITS-1:0];

    // ---- specials ----
    wire is_zero = (tekum_in == {N{1'b0}});
    wire is_nar  = (tekum_in == (1'b1 << (N-1)));

    // ===================================================================
    // TAPERED REGIME EXTRACTION
    // -------------------------------------------------------------------
    // r_eff = D ? R : ((REGIME_COUNT-1) - R)
    // p     = PAYLOAD_BITS - r_eff          // mantissa bits available (the taper)
    //
    // This is the heart of the tapered format: r_eff selects how many payload
    // bits are exponent (characteristic) vs mantissa. Near unity r_eff is small
    // -> p is large (high precision); at the extremes r_eff is large -> p small.
    //
    // TODO: verify from full paper -- the real tekum regime may use a balanced-
    // ternary run-length (trits) rather than the binary 3-bit R inherited from
    // takum. The arithmetic below is correct for the working binary-takum model
    // and matches conformance/tekum_ref.py; swapping in a ternary regime parser
    // is a localized change to r_eff computation.
    // ===================================================================
    wire [REGIME_BITS-1:0] r_comp = REGIME_COUNT[REGIME_BITS-1:0] - 1'b1 - R;
    wire [REGIME_BITS-1:0] r_eff_raw = D ? R : r_comp;

    // clamp r_eff to the available payload (degenerate guard for tiny formats)
    wire [7:0] payload_w = PAYLOAD_BITS[7:0];
    wire [7:0] r_eff_u8  = ({{(8-REGIME_BITS){1'b0}}, r_eff_raw} > payload_w)
                            ? payload_w
                            : {{(8-REGIME_BITS){1'b0}}, r_eff_raw};
    wire [7:0] p_bits    = payload_w - r_eff_u8;       // mantissa width (the TAPER)

    // ---- characteristic C_u (r_eff bits, above mantissa) and mantissa M_u (p bits) ----
    // payload layout (LSB-first): [ M_u (p bits) | C_u (r_eff bits) ]
    // C_u sits at bit offset p_bits; M_u occupies the low p_bits.
    // Variable-width extraction is not directly expressible in Verilog for
    // elaboration-time-constant widths only, so we use a barrel approach with
    // a function over the (max-width) payload, then resize.
    //
    // TODO: verify from full paper -- characteristic may carry a ternary sign
    //       (balanced ternary digits) rather than unsigned binary C_u.
    function [PAYLOAD_BITS-1:0] extract_C_u;
        input [PAYLOAD_BITS-1:0] pl;
        input [7:0] reff;
        integer mask;
        integer i;
        begin
            extract_C_u = {PAYLOAD_BITS{1'b0}};
            mask = (1 << reff) - 1;
            for (i = 0; i < PAYLOAD_BITS; i = i + 1)
                if (i >= p_bits && i < (p_bits + reff))
                    if (pl[i]) extract_C_u[i - p_bits] = 1'b1;
            // (mask applied implicitly by only reading reff bits)
        end
    endfunction

    wire [PAYLOAD_BITS-1:0] C_u_wide = extract_C_u(lower, r_eff_u8);
    wire [PAYLOAD_BITS-1:0] M_u_wide = lower & ((1 << p_bits) - 1);

    // ===================================================================
    // CHARACTERISTIC BIAS TABLE  (CBIAS[{D,R}])
    // -------------------------------------------------------------------
    // Inherited from fpga/openxc7-synth/takum64_decode.v:22-27 (binary parent).
    // TODO: verify from full paper -- tekum may use ternary-adapted biases.
    // ===================================================================
    wire signed [15:0] cbias;
    reg    signed [15:0] cbias_r;
    always @(*) begin
        case ({D, R})
            4'd0:  cbias_r = -16'sd255;
            4'd1:  cbias_r = -16'sd127;
            4'd2:  cbias_r = -16'sd63;
            4'd3:  cbias_r = -16'sd31;
            4'd4:  cbias_r = -16'sd15;
            4'd5:  cbias_r = -16'sd7;
            4'd6:  cbias_r = -16'sd3;
            4'd7:  cbias_r = -16'sd1;
            4'd8:  cbias_r = 16'sd0;
            4'd9:  cbias_r = 16'sd1;
            4'd10: cbias_r = 16'sd3;
            4'd11: cbias_r = 16'sd7;
            4'd12: cbias_r = 16'sd15;
            4'd13: cbias_r = 16'sd31;
            4'd14: cbias_r = 16'sd63;
            4'd15: cbias_r = 16'sd127;
            default: cbias_r = 16'sd0;
        endcase
    end
    assign cbias = cbias_r;

    // ---- unbiased exponent c = cbias + C_u ----
    // $signed(cbias) sign-extends the signed 16-bit bias; C_u_wide is unsigned
    // (zero-extended). NOTE: `$signed({const, signed_wire})` would NOT sign-extend
    // (concatenation is unsigned) -- the form below is correct.
    wire signed [31:0] c_unbiased =
        $signed(cbias) + $signed({{(32-PAYLOAD_BITS){1'b0}}, C_u_wide});

    // ===================================================================
    // MANTISSA with implicit leading bit
    // -------------------------------------------------------------------
    // Pack {1'b1, M_u} so the implicit leading bit sits at index p_bits within
    // mant_o, and expose p_bits as the MSB index for the downstream packer.
    // (mirrors the "full_sig = {1'b1, pack_frac}" idiom from gf_decode_param.v)
    // ===================================================================
    function [N-1:0] pack_implicit_mant;
        input [PAYLOAD_BITS-1:0] mu;
        input [7:0] pbits;
        integer k;
        begin
            pack_implicit_mant = {N{1'b0}};
            pack_implicit_mant[pbits] = 1'b1;            // implicit leading bit
            // Constant bound with a guard, not `k < pbits`. pbits is a runtime
            // input, and yosys rejects a non-constant procedural for-loop bound
            // outright -- "2nd expression of procedural for-loop is not constant"
            // -- so the whole file could not be read, and with it tekum16_adder.v,
            // which instantiates this module. iverilog accepts it, which is why a
            // parse guard built on iverilog never saw it. This is the same
            // constant-bound-plus-condition idiom extract_C_u already uses above.
            for (k = 0; k < PAYLOAD_BITS; k = k + 1)
                if (k < pbits)
                    pack_implicit_mant[k] = mu[k];       // M_u fraction bits
        end
    endfunction

    wire [N-1:0] mant_packed = pack_implicit_mant(M_u_wide, p_bits);

    // ---- output assignment ----
    assign sign_o          = S;
    assign exp_o           = c_unbiased;
    assign mant_o          = is_zero ? {N{1'b0}} : mant_packed;
    assign mant_msb_idx_o  = p_bits[7:0];
    assign is_nar_o        = is_nar;
    assign is_zero_o       = is_zero;
    assign is_finite_o     = !is_nar & !is_zero;

    // ===================================================================
    // OPTIONAL FP32 PACK PATH  (structural stub)
    // -------------------------------------------------------------------
    // Assembling binary32 from a TAPERED source requires re-quantizing the p-bit
    // mantissa to 23 bits (left-justify p_bits into the FP32 fraction field) and
    // applying gradual-underflow when c_unbiased falls below -126, exactly as in
    // gf_decode_param.v's shared significand packer. That datapath is LEFT AS
    // TODO here pending verification of the tekum exponent scaling law.
    //
    // TODO: verify from full paper, then port the FP32 packer from
    //       gf_decode_param.v (norm_widen_result / sub_shifted logic) using
    //       p_bits as the source mantissa width and c_unbiased as the exponent.
    // ===================================================================
    localparam [31:0] FP32_QNAN    = 32'h7FC00001;
    localparam [31:0] FP32_POS_INF = 32'h7F800000;
    localparam [31:0] FP32_NEG_INF = 32'hFF800000;

    reg [31:0] fp32_r;
    always @(*) begin
        fp32_r = 32'h00000000;
        if (is_nar)
            fp32_r = FP32_QNAN;
        else if (is_zero)
            fp32_r = {S, 31'b0};
        else begin
            // TODO: verify from full paper -- full tapered->FP32 pack datapath.
            // Placeholder: emit sign + biased exponent, zero fraction for now
            // (NOT bit-exact; replaced by the ported gf_decode_param.v packer
            // once the tekum exponent scaling is confirmed).
            if (c_unbiased > 127)
                fp32_r = S ? FP32_NEG_INF : FP32_POS_INF;
            else if (c_unbiased < -126)
                fp32_r = {S, 31'b0};                      // flush (TODO: gradual underflow)
            else
                fp32_r = {S, c_unbiased[7:0] + 8'd127, 23'b0};  // TODO: insert mantissa
        end
    end

    // -------------------------------------------------------------------
    // Optional output register
    // -------------------------------------------------------------------
    generate
        if (OUT_REG != 0) begin : g_reg
            reg        sign_q;
            reg signed [31:0] exp_q;
            reg [N-1:0] mant_q;
            reg [7:0]   msb_q;
            reg         nar_q, zero_q, fin_q;
            reg [31:0]  fp32_q;
            always @(posedge clk) begin
                if (!rst_n) begin
                    sign_q <= 1'b0; exp_q <= 32'b0; mant_q <= {N{1'b0}};
                    msb_q <= 8'b0; nar_q <= 1'b0; zero_q <= 1'b0; fin_q <= 1'b0;
                    fp32_q <= 32'b0;
                end else begin
                    sign_q <= sign_o; exp_q <= exp_o; mant_q <= mant_o;
                    msb_q  <= mant_msb_idx_o;
                    nar_q  <= is_nar_o; zero_q <= is_zero_o; fin_q <= is_finite_o;
                    fp32_q <= fp32_r;
                end
            end
            // registered outputs shadow the combinational ones in this stub;
            // a production version exposes them on distinct ports.
        end
    endgenerate

endmodule
`default_nettype wire
