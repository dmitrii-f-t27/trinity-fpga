`default_nettype none
`timescale 1ns / 1ps
// ============================================================================
// takum16_native_mul.v — NATIVE logarithmic-domain multiplier for takum16
// (Hunhold arXiv:2404.18603).
//
// In the LNS interpretation validated on Trinity silicon
// (fpga/openxc7-synth/takum16_lut.mem: value = (-1)^S * exp(ell/2),
// ell = (1-2S)*(c+m)), MULTIPLICATION reduces to:
//     result_sign = Sa ^ Sb
//     ell_result  = ell_a + ell_b          (one signed fixed-point add)
//     repack      = tapered re-encode of (1-2*Sr)*ell_result
// NO mantissa multiplier, NO DSP, NO BRAM. One adder + regime re-selection.
//
// VERIFICATION MODEL
//   This core implements the LOG (exp(ell/2)) model — the same second-witness
//   used by takum16_decode.v's BRAM LUT, hence bit-exact vs the HW decode path.
//   It is NOT bit-exact vs conformance/takum_ref.py, which deliberately uses a
//   LINEAR (1+M)*2^c working model (see that file's header). The two models
//   agree on the raw result iff both operands have a zero mantissa (exact
//   power-of-two encodings), e.g. 0x4800*0x4800=0x4C00 under both. See
//   research/TAKUM_VS_GF_BENCHMARK.md (Honesty section).
//
// AXI-Stream handshake mirrors gf_mul_param.v (1-deep output register) so the
// LUT measurement is directly comparable to the GF16 multiplier.
//
// Honesty: Trinity conformance team (Agent F). [modeled], not silicon.
// ============================================================================
module takum16_native_mul (
    input  wire        clk,
    input  wire        rst,
    input  wire        in_valid,
    input  wire [15:0] in_a,
    input  wire [15:0] in_b,
    output wire        in_ready,
    output reg         out_valid,
    output reg  [15:0] out_y,
    input  wire        out_ready
);

    // ------------------------------------------------------------------
    // field tables (regime_bits=3, overhead=5, payload=11, pmax=11)
    // ------------------------------------------------------------------
    function [2:0] reff_f;   // r_eff from {D,R}
        input D; input [2:0] R;
        reff_f = D ? R : (3'd7 - R);
    endfunction
    function [3:0] pf_f;     // p = 11 - r_eff  (always in [4,11])
        input D; input [2:0] R;
        reg [2:0] re;
        begin re = D ? R : (3'd7 - R); pf_f = 4'd11 - {1'b0, re}; end
    endfunction
    function signed [9:0] cbias_f;   // CBIAS[{D,R}]
        input D; input [2:0] R;
        begin
            case ({D, R})
                4'b0000: cbias_f = -10'sd255;
                4'b0001: cbias_f = -10'sd127;
                4'b0010: cbias_f = -10'sd063;
                4'b0011: cbias_f = -10'sd031;
                4'b0100: cbias_f = -10'sd015;
                4'b0101: cbias_f = -10'sd007;
                4'b0110: cbias_f = -10'sd003;
                4'b0111: cbias_f = -10'sd001;
                4'b1000: cbias_f = 10'sd000;
                4'b1001: cbias_f = 10'sd001;
                4'b1010: cbias_f = 10'sd003;
                4'b1011: cbias_f = 10'sd007;
                4'b1100: cbias_f = 10'sd015;
                4'b1101: cbias_f = 10'sd031;
                4'b1110: cbias_f = 10'sd063;
                default: cbias_f = 10'sd127;
            endcase
        end
    endfunction

    // regime selection from signed characteristic c. The 16 regimes form a
    // contiguous, NON-overlapping partition of c in [-255,254]; returns {D,R}
    // with saturation at the extremes.
    function [3:0] regime_f;
        input signed [15:0] c;
        begin
            if (c >= 0) begin
                if      (c <= 16'sd0000) regime_f = {1'b1, 3'd0};
                else if (c <= 16'sd0002) regime_f = {1'b1, 3'd1};
                else if (c <= 16'sd0006) regime_f = {1'b1, 3'd2};
                else if (c <= 16'sd0014) regime_f = {1'b1, 3'd3};
                else if (c <= 16'sd0030) regime_f = {1'b1, 3'd4};
                else if (c <= 16'sd0062) regime_f = {1'b1, 3'd5};
                else if (c <= 16'sd0126) regime_f = {1'b1, 3'd6};
                else                     regime_f = {1'b1, 3'd7};
            end else begin
                if      (c >= -16'sd0001) regime_f = {1'b0, 3'd7};
                else if (c >= -16'sd0003) regime_f = {1'b0, 3'd6};
                else if (c >= -16'sd0007) regime_f = {1'b0, 3'd5};
                else if (c >= -16'sd0015) regime_f = {1'b0, 3'd4};
                else if (c >= -16'sd0031) regime_f = {1'b0, 3'd3};
                else if (c >= -16'sd0063) regime_f = {1'b0, 3'd2};
                else if (c >= -16'sd0127) regime_f = {1'b0, 3'd1};
                else                      regime_f = {1'b0, 3'd0};
            end
        end
    endfunction

    // decode one operand to signed fixed-point q = (cbias+Cu) + Mu/2^p
    // in units of 2^-11.  (shifts/masks instead of variable part-selects)
    function signed [21:0] qdecode;
        input [15:0] raw;
        reg Dg; reg [2:0] Rg, reg_; reg [3:0] pg;
        reg signed [9:0] cb, cint;
        reg [10:0] pay, Mu; reg [6:0] Cu;
        reg [17:0] frac;
        begin
            Dg   = raw[14];
            Rg   = raw[13:11];
            reg_ = reff_f(Dg, Rg);
            pg   = pf_f(Dg, Rg);
            cb   = cbias_f(Dg, Rg);
            pay  = raw[10:0];
            Cu   = pay >> pg;                          // top r_eff bits
            Mu   = pay & (11'h7FF >> (4'd11 - pg));    // bottom pg bits
            cint = cb + $signed({3'b0, Cu});
            frac = {7'b0, Mu} << (4'd11 - pg);         // Mu aligned to 2^-11 grid
            qdecode = (cint <<< 11) + $signed(frac);
        end
    endfunction

    // pack {Sr,D,R,Cu,Mu} into raw16 ; payload = Cu<<p | Mu (11 bits)
    function [15:0] pack16;
        input Sr; input D; input [2:0] R; input [6:0] Cu; input [10:0] Mu;
        input [3:0] pg; input [2:0] reg_;
        reg [10:0] pay; reg [17:0] cupart;
        begin
            cupart = (reg_ != 0) ? ({11'b0, Cu} << pg) : 18'd0;
            pay    = (cupart[10:0] | Mu) & 11'h7FF;
            pack16 = {Sr, D, R, pay};
        end
    endfunction

    // ------------------------------------------------------------------
    // operand taps + fixed-point ell arithmetic
    // ------------------------------------------------------------------
    wire Sa = in_a[15], Sb = in_b[15];
    wire a_nar  = (in_a == 16'h8000);
    wire b_nar  = (in_b == 16'h8000);
    wire a_zero = (in_a == 16'h0000);
    wire b_zero = (in_b == 16'h0000);
    wire Sr = Sa ^ Sb;

    wire signed [21:0] qa = qdecode(in_a);
    wire signed [21:0] qb = qdecode(in_b);

    // ell = (1-2S)*q ; |a*b| = exp((ell_a+ell_b)/2)
    wire signed [21:0] ell_a = Sa ? -qa : qa;
    wire signed [21:0] ell_b = Sb ? -qb : qb;
    wire signed [22:0] ell_sum = $signed(ell_a) + $signed(ell_b);
    wire signed [22:0] qr = Sr ? -ell_sum : ell_sum;   // q_result = (1-2Sr)*ell_sum

    wire signed [15:0] c_r = $signed(qr >>> 11);        // characteristic (floor)
    wire [10:0]        m_r = qr[10:0];                  // fraction * 2^11

    // ------------------------------------------------------------------
    // combinational core: tapered re-encode + RNE + carry handling
    // ------------------------------------------------------------------
    reg [15:0] result_packed;

    reg signed [15:0] c0, c1;
    reg [3:0]  dr0, dr1;
    reg [2:0]  re0, re1;
    reg [3:0]  p0, p1;
    reg signed [9:0]  cb0, cb1;
    reg signed [12:0] cu0, cu1;
    reg [10:0] mu0, mu1, kept, mshifted;
    reg [6:0]  shift;
    reg        rnd_half, sticky, rnd_up, mcarry, ccarry;

    always @(*) begin
        result_packed = 16'h0000;

        if (a_nar || b_nar) begin
            result_packed = 16'h8000;                    // NaR propagates
        end else if (a_zero || b_zero) begin
            result_packed = 16'h0000;                    // takum has no -0
        end else begin
            c0  = c_r;
            dr0 = regime_f(c0);
            re0 = reff_f(dr0[3], dr0[2:0]);
            p0  = pf_f(dr0[3], dr0[2:0]);
            cb0 = cbias_f(dr0[3], dr0[2:0]);
            cu0 = c0 - cb0;

            // mantissa RNE on the (11 - p0) discarded low bits of m_r
            shift    = 4'd11 - p0;
            mshifted = m_r >> shift;
            kept     = mshifted;
            rnd_half = shift ? ((m_r >> (shift - 7'd1)) & 11'h1) : 1'b0;
            sticky   = (shift >= 7'd2) ? (|(m_r & (11'h7FF >> (4'd11 - (shift - 7'd1))))) : 1'b0;
            rnd_up   = rnd_half & (sticky | kept[0]);    // round-half-to-even
            mu0      = kept + {10'b0, rnd_up};
            mcarry   = ({1'b0, mu0} == (12'd1 << p0));   // 2^p0 needs p0+1 bits

            if (mcarry) begin
                mu0 = 11'd0;
                cu1 = cu0 + 13'sd1;
            end else begin
                cu1 = cu0;
            end
            ccarry = (cu1 == $signed(13'd1 << re0));

            if (ccarry) begin
                c1  = c0 + 16'sd1;
                dr1 = regime_f(c1);
                re1 = reff_f(dr1[3], dr1[2:0]);
                p1  = pf_f(dr1[3], dr1[2:0]);
                cb1 = cbias_f(dr1[3], dr1[2:0]);
                cu1 = c1 - cb1;
                mu1 = 11'd0;
                if (c1 > 16'sd0254) begin
                    result_packed = {Sr, 1'b1, 3'd7, 11'h7FF};      // saturate max
                end else begin
                    result_packed = pack16(Sr, dr1[3], dr1[2:0], cu1[6:0], mu1, p1, re1);
                end
            end else begin
                if (c0 > 16'sd0254) begin
                    result_packed = {Sr, 1'b1, 3'd7, 11'h7FF};      // overflow -> max
                end else if (c0 < -16'sd0255) begin
                    result_packed = 16'h0000;                       // underflow -> +0
                end else begin
                    result_packed = pack16(Sr, dr0[3], dr0[2:0], cu1[6:0], mu0, p0, re0);
                end
            end
        end
    end

    // ------------------------------------------------------------------
    // AXI-Stream output register (mirrors gf_mul_param.v: 1-deep buffer)
    // ------------------------------------------------------------------
    reg [15:0] out_reg;
    reg        out_valid_reg;
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            out_reg <= 16'h0000; out_valid_reg <= 1'b0;
        end else begin
            if (out_valid_reg && out_ready) out_valid_reg <= 1'b0;
            if (in_valid && in_ready) begin
                out_reg <= result_packed; out_valid_reg <= 1'b1;
            end
        end
    end
    assign in_ready  = ~out_valid_reg | out_ready;
    assign out_valid = out_valid_reg;
    always @(*) out_y = out_reg;

endmodule
`default_nettype none
