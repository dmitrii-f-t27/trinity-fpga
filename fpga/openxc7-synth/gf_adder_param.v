`timescale 1ns / 1ps
// Parameterized GoldenFloat ADD — works for GF4 (1S+1E+2M) through GF64 (1S+24E+39M).
// Same algorithm as gf16_adder.v: align exp -> effective add/sub -> normalize -> pack.
// Round-half-to-even (RNE) with GRS (G=bit2, R=bit1, S=bit0). AXI-Stream handshake identical to gf16_adder.
//
// PIPELINE parameter (default 0 = backward compatible):
//   PIPELINE=0 : single-cycle combinational datapath, registered output (1-cycle latency).
//                Used by GF4..GF32 wrappers — these meet timing on XC7A200T CFGMCLK.
//   PIPELINE=1 : 2-stage pipeline. Stage 1 = field extract + zero/denorm/NaN/Inf detect +
//                effective exp + mantissa extend + barrel shift + sticky (registered).
//                Stage 2 = add/sub + normalize + round + pack (registered). 2-cycle latency.
//                in_ready = ~pipe_valid | (pipe_valid & ~out_valid_reg) — accept when the
//                2-deep FIFO has space. Required for GF64 (43-bit shifter + 64-bit priority
//                encoder too deep for CFGMCLK; silicon 70.1% pass without pipelining).
module gf_adder_param #(
    parameter EXP_BITS  = 6,
    parameter MANT_BITS = 8,
    parameter TOTAL     = 1 + EXP_BITS + MANT_BITS,  // total operand width
    parameter BIAS      = (1 << (EXP_BITS - 1)) - 1,
    // HAS_INF=1 only for formats where exp=all-ones is reserved as SPECIAL
    //   (Inf/NaN): currently GF16 (gf16.t27:25,35,131). For GF6/8/12/20
    //   exp=all-ones is a FINITE max_value (gf8.t27:115-119) -> HAS_INF=0,
    //   overflow saturates to max-finite.
    parameter HAS_INF   = 0,
    // PIPELINE=1 splits the combinational path into 2 stages for wide formats (GF64).
    // See header comment for details. Default 0 preserves all existing behavior.
    parameter PIPELINE  = 0
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
`ifdef FORMAL
    // Formal-only observation tap: exposes the combinational core (result_packed)
    // so a clockless miter (formal/gf_adder_comb_miter.v) can prove
    // result_packed == independent RNE oracle for ALL input pairs without the
    // reset/init-state artifact of a sequential harness. Production synthesis
    // never defines FORMAL -> this port is absent -> zero impact on the datapath.
    ,
    output wire [TOTAL-1:0]        result_comb
`endif
);
    // Field extraction
    wire                        sa = in_a[TOTAL-1];
    wire [EXP_BITS-1:0]         ea = in_a[TOTAL-2:MANT_BITS];
    wire [MANT_BITS-1:0]        ma = in_a[MANT_BITS-1:0];
    wire                        sb = in_b[TOTAL-1];
    wire [EXP_BITS-1:0]         eb = in_b[TOTAL-2:MANT_BITS];
    wire [MANT_BITS-1:0]        mb = in_b[MANT_BITS-1:0];

    // Zero detection: both +0 (all bits 0) and -0 (sign=1, exp=0, mant=0)
    wire                        a_zero = (ea == {EXP_BITS{1'b0}}) && (ma == {MANT_BITS{1'b0}});
    wire                        b_zero = (eb == {EXP_BITS{1'b0}}) && (mb == {MANT_BITS{1'b0}});

    // Denormal detection: exp_field==0 && mant!=0. (Dropped the bias>0 guard: per the
    // gf_ref.py golden, exp=0,mant!=0 is a DENORMAL for ALL widths including GF4 (bias=0) —
    // value = mant/2^MANT * 2^(1-bias). The old guard sent GF4 exp=0,mant!=0 to the normal
    // path with sh=ea-1=-1 => negative shift (undefined). No-op for BIAS>0 formats where the
    // guard was always true, so GF6/8/12/16 netlists are unchanged.)
    wire a_denorm = (ea == {EXP_BITS{1'b0}}) && (ma != {MANT_BITS{1'b0}});
    wire b_denorm = (eb == {EXP_BITS{1'b0}}) && (mb != {MANT_BITS{1'b0}});

    // NaN input detection (HAS_INF only — GF16): exp=all-ones && mant!=0.
    // Without this, NaN inputs fall into the normal path and produce Inf (overflow),
    // violating IEEE 754 (NaN+x = NaN). Caught by HW flash burst (fire #56).
    wire a_nan = (HAS_INF != 0) && (ea == {EXP_BITS{1'b1}}) && (ma != {MANT_BITS{1'b0}});
    wire b_nan = (HAS_INF != 0) && (eb == {EXP_BITS{1'b1}}) && (mb != {MANT_BITS{1'b0}});

    // Inf input detection (HAS_INF only — GF16): exp=all-ones && mant==0.
    // WV-22 fix: without this, an Inf operand fell into the normal path and
    // produced a FINITE saturated value instead of propagating Inf, violating
    // IEEE 754 (Inf+x=Inf, Inf+(-Inf)=NaN). NaN has priority over Inf below.
    // Proven against gf_ref.gf_add golden on all gf16 special inputs (0 mismatch).
    wire a_inf = (HAS_INF != 0) && (ea == {EXP_BITS{1'b1}}) && (ma == {MANT_BITS{1'b0}});
    wire b_inf = (HAS_INF != 0) && (eb == {EXP_BITS{1'b1}}) && (mb == {MANT_BITS{1'b0}});

    // Effective exponent: denormals use 1 (not 0) for alignment — their real_exp = 1-BIAS
    wire [EXP_BITS-1:0] ea_eff = a_denorm ? {{(EXP_BITS-1){1'b0}}, 1'b1} : ea;
    wire [EXP_BITS-1:0] eb_eff = b_denorm ? {{(EXP_BITS-1){1'b0}}, 1'b1} : eb;

    // Mantissa: denormals have NO implicit 1 ({0, ma} instead of {1, ma})
    wire [MANT_BITS:0]   ma_f = a_denorm ? {1'b0, ma} : {1'b1, ma};
    wire [MANT_BITS:0]   mb_f = b_denorm ? {1'b0, mb} : {1'b1, mb};

    wire a_larger = (ea_eff > eb_eff) || ((ea_eff == eb_eff) && (ma_f >= mb_f));
    wire [EXP_BITS:0] ediff = a_larger ?
        ({1'b0, ea_eff} - {1'b0, eb_eff}) : ({1'b0, eb_eff} - {1'b0, ea_eff});

    // NOTE: A clamp (ediff_shift = min(ediff, MANT_BITS+4)) was tried in Wave 4
    // to reduce barrel shifter depth. It fixed -0+0 but regressed overall
    // silicon from 70.1% to 48.9% (yosys reroutes differently). Reverted.
    // Future: 2-stage pipeline is the definitive fix for GF64+ timing.

    // Sticky: OR of all bits below G+R from the SMALLER operand (the shifted one)
    reg sticky_bit;
    integer j;
    always @(*) begin
        sticky_bit = 1'b0;
        for (j = 0; j <= MANT_BITS; j = j + 1)
            if (j < $signed(ediff) - 2)
                sticky_bit = sticky_bit | (a_larger ? mb_f[j] : ma_f[j]);
    end

    // Extend to MANT_BITS+4, align, preserve G+R+S
    wire [MANT_BITS+3:0] ma_ext = {ma_f, 3'b000};
    wire [MANT_BITS+3:0] mb_ext = {mb_f, 3'b000};
    wire [MANT_BITS+3:0] ma_al_raw = a_larger ? ma_ext : (ma_ext >> ediff);
    wire [MANT_BITS+3:0] mb_al_raw = a_larger ? (mb_ext >> ediff) : mb_ext;
    // Inject sticky into the SHIFTED operand's bit 0
    wire [MANT_BITS+3:0] ma_al = a_larger ? ma_ext : {ma_al_raw[MANT_BITS+3:1], ma_al_raw[0] | sticky_bit};
    wire [MANT_BITS+3:0] mb_al = a_larger ? {mb_al_raw[MANT_BITS+3:1], mb_al_raw[0] | sticky_bit} : mb_ext;

    wire [EXP_BITS-1:0]  er   = a_larger ? ea_eff : eb_eff;
    wire                 sr   = a_larger ? sa : sb;

    wire                  same_sign = (sa == sb);
    wire [MANT_BITS+4:0]  sum_add = {1'b0, ma_al} + {1'b0, mb_al};
    wire [MANT_BITS+4:0]  sum_sub = a_larger ?
        ({1'b0, ma_al} - {1'b0, mb_al}) :
        ({1'b0, mb_al} - {1'b0, ma_al});
    wire [MANT_BITS+4:0]  mant_raw = same_sign ? sum_add : sum_sub;

    reg  [TOTAL-1:0]      result_packed;
    reg  [MANT_BITS+4:0]  mw;
    reg  [EXP_BITS:0]     ew;
    reg                    sg;
    reg                    underflow;
    reg  [MANT_BITS+1:0]  mant_rounded;
    reg                    old_sticky;
    integer i;

    always @(*) begin
        // NaN input → canonical quiet NaN (IEEE 754: NaN propagates through ADD).
        // MUST precede zero-passthrough: 0+NaN and NaN+0 must yield canonical qNaN
        // ({0,all-ones-exp,0..0,1}), NOT the raw NaN operand. Previously the
        // a_zero/b_zero branch returned in_b/in_a verbatim, so a zero paired with a
        // NaN leaked the non-canonical NaN payload (gf16-sub 4/512 fail, all four
        // vectors had one zero + one NaN operand). No-op for HAS_INF=0 formats
        // (a_nan/b_nan are then tied to 0).
        if (a_nan || b_nan)
            result_packed = {1'b0, {EXP_BITS{1'b1}}, {(MANT_BITS-1){1'b0}}, 1'b1};
        // ----- zero-passthrough with IEEE zero-sign (gf16.t27:219, RNE) -----
        // (+/-0)+(+/-0): -0 only if BOTH operands are -0, else +0.
        // x + (+/-0) = x for nonzero x (passthrough preserves sign of x).
        else if (a_zero && b_zero)
            result_packed = (sa && sb) ? {1'b1, {(TOTAL-1){1'b0}}} : {TOTAL{1'b0}};
        else if (a_zero)
            result_packed = in_b;
        else if (b_zero)
            result_packed = in_a;
        // Inf input (WV-22 fix, NaN already handled above so neither is NaN here):
        //   Inf + (-Inf) = NaN; Inf(+/-) + Inf(same) = Inf(same); Inf + finite = Inf.
        else if (a_inf && b_inf)
            result_packed = (sa != sb)
                ? {1'b0, {EXP_BITS{1'b1}}, {(MANT_BITS-1){1'b0}}, 1'b1}   // Inf+(-Inf)=qNaN
                : {sa,   {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};              // +/-Inf
        else if (a_inf)
            result_packed = {sa, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};     // Inf + finite = Inf
        else if (b_inf)
            result_packed = {sb, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};     // finite + Inf = Inf
        else begin
            sg = sr; mw = mant_raw; ew = {1'b0, er}; underflow = 1'b0;
            // Add overflow (preserve sticky: capture old bit[0], OR into new sticky after >>1)
            if (same_sign && mw[MANT_BITS+4]) begin
                old_sticky = mw[0];
                mw = mw >> 1;
                mw[0] = mw[0] | old_sticky;
                ew = ew + 1;
            end
            // Subtraction normalize — stop at ew==0 (do NOT over-shift past the
            // denormal boundary; a subnormal result is packed as denormal below).
            if (!same_sign && mw != 0)
                for (i = 0; i < MANT_BITS+3; i = i + 1)
                    if (!mw[MANT_BITS+3] && ew != 0) begin
                        mw = mw << 1;
                        ew = ew - 1;
                    end
            // Subtraction subnormal result (ew==0): after normalize the denormal
            // mantissa sits one bit high; right-shift by 1 (sticky-preserving) to
            // align with the ew==0 denormal pack path. (er-independent: the offset
            // is GRS_width+1 regardless of exponent/MANT_BITS.)
            if (!same_sign && mw != 0 && ew == 0) begin
                old_sticky = mw[0];
                mw = mw >> 1;
                mw[0] = mw[0] | old_sticky;
            end
            // Round-half-to-even using G(bit2) R(bit1) S(bit0)
            if (mw[2] && (mw[1] || mw[0] || mw[3]))
                mant_rounded = mw[MANT_BITS+3:3] + 1;
            else
                mant_rounded = mw[MANT_BITS+3:3];
            if (mant_rounded[MANT_BITS+1]) begin
                mant_rounded = mant_rounded >> 1;
                ew = ew + 1;
            end
            // Denormal result detection (addition only, same_sign). Applies to ALL
            // widths incl. GF4 (BIAS=0): a same-sign sum whose leading bit sits below
            // the implicit position (mw[MANT_BITS+3]==0) with ew<=1 is a denormal result.
            if (same_sign && !mw[MANT_BITS+3] && ew <= 1'b1)
                ew = {EXP_BITS{1'b0}};  // force denormal packing
            // Pack
            if (mw == 0 || underflow)
                result_packed = {TOTAL{1'b0}};   // cancellation/zero -> +0 (sg=0)
            // OVERFLOW per spec (family-split):
            //  HAS_INF (gf16): exp=all-ones reserved -> overflow on carry-out
            //    OR ew_field==all-ones -> Inf {sg, all-ones-exp, 0...0}
            //  no-Inf (gf6/8/12/20): exp=all-ones is finite max -> overflow only
            //    on carry-out -> saturate {sg, all-ones-exp, all-ones-mant}
            else if (HAS_INF && (ew[EXP_BITS] || (ew[EXP_BITS-1:0] == {EXP_BITS{1'b1}})))
                result_packed = {sg, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};   // +/-Inf
            else if (!HAS_INF && ew[EXP_BITS])
                result_packed = {sg, {EXP_BITS{1'b1}}, {MANT_BITS{1'b1}}};   // max-finite
            else if (ew == {EXP_BITS{1'b0}})
                result_packed = {sg, {EXP_BITS{1'b0}}, mant_rounded[MANT_BITS-1:0]};
            else
                result_packed = {sg, ew[EXP_BITS-1:0], mant_rounded[MANT_BITS-1:0]};
        end
    end

    // AXI-Stream output register
    reg [TOTAL-1:0] out_reg;
    reg             out_valid_reg;
    // pipe_valid: stage-1 register occupancy (PIPELINE=1 only; held at 0 otherwise
    // so the in_ready formula degrades to the original ~out_valid_reg | out_ready).
    reg             pipe_valid;

    generate
        if (PIPELINE) begin : g_pipe
            // ====== STAGE 1 REGISTERS (latched at posedge when accepting input) ======
            // Capture everything phase-1 produces that stage 2 needs:
            //   - datapath: mant_raw (post-align add/sub operand), same_sign, er, sr
            //   - special-case flags + raw operands (for IEEE passthrough in stage 2)
            reg [MANT_BITS+4:0] s1_mant_raw;
            reg                 s1_same_sign;
            reg [EXP_BITS-1:0]  s1_er;
            reg                 s1_sr;
            reg                 s1_a_zero, s1_b_zero;
            reg                 s1_a_nan,  s1_b_nan;
            reg                 s1_a_inf,  s1_b_inf;
            reg                 s1_sa,     s1_sb;
            reg [TOTAL-1:0]     s1_in_a,   s1_in_b;

            // ====== STAGE 2 COMBINATIONAL: add/sub + normalize + round + pack ======
            // Mirror of the PIPELINE=0 result_packed block but reading from s1_* regs.
            // Special-case order (NaN > zero > Inf > normal) is preserved exactly.
            reg [TOTAL-1:0]     result_packed_pipe;
            reg [MANT_BITS+4:0] mw_p;
            reg [EXP_BITS:0]    ew_p;
            reg                 sg_p;
            reg                 underflow_p;
            reg [MANT_BITS+1:0] mant_rounded_p;
            reg                 old_sticky_p;
            integer i_p;

            always @(*) begin
                if (s1_a_nan || s1_b_nan)
                    result_packed_pipe = {1'b0, {EXP_BITS{1'b1}}, {(MANT_BITS-1){1'b0}}, 1'b1};
                else if (s1_a_zero && s1_b_zero)
                    result_packed_pipe = (s1_sa && s1_sb) ? {1'b1, {(TOTAL-1){1'b0}}} : {TOTAL{1'b0}};
                else if (s1_a_zero)
                    result_packed_pipe = s1_in_b;
                else if (s1_b_zero)
                    result_packed_pipe = s1_in_a;
                else if (s1_a_inf && s1_b_inf)
                    result_packed_pipe = (s1_sa != s1_sb)
                        ? {1'b0, {EXP_BITS{1'b1}}, {(MANT_BITS-1){1'b0}}, 1'b1}
                        : {s1_sa,   {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};
                else if (s1_a_inf)
                    result_packed_pipe = {s1_sa, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};
                else if (s1_b_inf)
                    result_packed_pipe = {s1_sb, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};
                else begin
                    sg_p = s1_sr; mw_p = s1_mant_raw; ew_p = {1'b0, s1_er}; underflow_p = 1'b0;
                    if (s1_same_sign && mw_p[MANT_BITS+4]) begin
                        old_sticky_p = mw_p[0];
                        mw_p = mw_p >> 1;
                        mw_p[0] = mw_p[0] | old_sticky_p;
                        ew_p = ew_p + 1;
                    end
                    if (!s1_same_sign && mw_p != 0)
                        for (i_p = 0; i_p < MANT_BITS+3; i_p = i_p + 1)
                            if (!mw_p[MANT_BITS+3] && ew_p != 0) begin
                                mw_p = mw_p << 1;
                                ew_p = ew_p - 1;
                            end
                    if (!s1_same_sign && mw_p != 0 && ew_p == 0) begin
                        old_sticky_p = mw_p[0];
                        mw_p = mw_p >> 1;
                        mw_p[0] = mw_p[0] | old_sticky_p;
                    end
                    if (mw_p[2] && (mw_p[1] || mw_p[0] || mw_p[3]))
                        mant_rounded_p = mw_p[MANT_BITS+3:3] + 1;
                    else
                        mant_rounded_p = mw_p[MANT_BITS+3:3];
                    if (mant_rounded_p[MANT_BITS+1]) begin
                        mant_rounded_p = mant_rounded_p >> 1;
                        ew_p = ew_p + 1;
                    end
                    if (s1_same_sign && !mw_p[MANT_BITS+3] && ew_p <= 1'b1)
                        ew_p = {EXP_BITS{1'b0}};
                    if (mw_p == 0 || underflow_p)
                        result_packed_pipe = {TOTAL{1'b0}};
                    else if (HAS_INF && (ew_p[EXP_BITS] || (ew_p[EXP_BITS-1:0] == {EXP_BITS{1'b1}})))
                        result_packed_pipe = {sg_p, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};
                    else if (!HAS_INF && ew_p[EXP_BITS])
                        result_packed_pipe = {sg_p, {EXP_BITS{1'b1}}, {MANT_BITS{1'b1}}};
                    else if (ew_p == {EXP_BITS{1'b0}})
                        result_packed_pipe = {sg_p, {EXP_BITS{1'b0}}, mant_rounded_p[MANT_BITS-1:0]};
                    else
                        result_packed_pipe = {sg_p, ew_p[EXP_BITS-1:0], mant_rounded_p[MANT_BITS-1:0]};
                end
            end

            // ====== STAGE 1 + OUTPUT REGISTER CONTROL ======
            // 2-deep registered pipeline with AXI-Stream backpressure.
            //   s2_writable = stage 2 can accept stage-1's value this cycle
            //               = ~out_valid_reg | out_ready
            //   in_ready    = ~pipe_valid | (pipe_valid & ~out_valid_reg)
            //                (spec formula — conservative; yields 1-cycle bubble when
            //                 both stages fill, irrelevant for UART-driven GF64 frames)
            always @(posedge clk or posedge rst) begin
                if (rst) begin
                    out_reg       <= {TOTAL{1'b0}};
                    out_valid_reg <= 1'b0;
                    pipe_valid    <= 1'b0;
                end else begin
                    // ---- Stage 2 (output register) ----
                    if (pipe_valid && (~out_valid_reg | out_ready)) begin
                        // Stage 2 <- stage 1 result
                        out_reg       <= result_packed_pipe;
                        out_valid_reg <= 1'b1;
                    end else if (out_valid_reg && out_ready) begin
                        // Stage 2 drained, no replacement from stage 1
                        out_valid_reg <= 1'b0;
                    end
                    // else: stage 2 holds (backpressure)

                    // ---- Stage 1 ----
                    if (in_valid && (~pipe_valid | ~out_valid_reg)) begin
                        // Accept new operands (in_ready=1 path)
                        s1_mant_raw  <= mant_raw;
                        s1_same_sign <= same_sign;
                        s1_er        <= er;
                        s1_sr        <= sr;
                        s1_a_zero    <= a_zero;
                        s1_b_zero    <= b_zero;
                        s1_a_nan     <= a_nan;
                        s1_b_nan     <= b_nan;
                        s1_a_inf     <= a_inf;
                        s1_b_inf     <= b_inf;
                        s1_sa        <= sa;
                        s1_sb        <= sb;
                        s1_in_a      <= in_a;
                        s1_in_b      <= in_b;
                        pipe_valid   <= 1'b1;
                    end else if (pipe_valid && (~out_valid_reg | out_ready)) begin
                        // Stage 1 drained into stage 2, no new input
                        pipe_valid <= 1'b0;
                    end
                    // else: stage 1 holds (backpressure)
                end
            end
        end else begin : g_nopipe
            // ====== ORIGINAL PIPELINE=0 OUTPUT REGISTER (unchanged) ======
            always @(posedge clk or posedge rst) begin
                if (rst) begin
                    out_reg       <= {TOTAL{1'b0}};
                    out_valid_reg <= 1'b0;
                    pipe_valid    <= 1'b0;
                end else begin
                    if (out_valid_reg && out_ready)
                        out_valid_reg <= 1'b0;
                    if (in_valid && in_ready) begin
                        out_reg       <= result_packed;
                        out_valid_reg <= 1'b1;
                    end
                end
            end
        end
    endgenerate

    // in_ready: spec formula when PIPELINE=1, original when PIPELINE=0.
    // (Elaboration-time constant fold — synthesizer picks one branch.)
    assign in_ready  = PIPELINE
        ? (~pipe_valid | (pipe_valid & ~out_valid_reg))
        : (~out_valid_reg | out_ready);
    assign out_valid = out_valid_reg;
    assign out_y     = out_reg;
`ifdef FORMAL
    assign result_comb = result_packed;   // combinational core tap (formal only)
`endif
endmodule
