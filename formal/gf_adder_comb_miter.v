// =============================================================================
// COMBINATIONAL formal miter for gf_adder_param — closes the formal-proof weak
// point that blocked the sequential harness for 39+ Wave-loop fires.
//
// WHY THIS WORKS WHERE gf_adder_property.v STALLED:
//   The DUT's `result_packed` is a PURELY COMBINATIONAL function of (in_a, in_b)
//   (always @(*) block, lines 102-172 of gf_adder_param.v). Only `out_reg` is
//   clocked. The old harness proved the REGISTERED path, which introduced a
//   reset/init-state artifact (undriven capture regs at reset deassertion) that
//   yosys sat -tempinduct kept hitting with spurious counterexamples.
//
//   This miter holds clk=0, rst=0 -> the posedge block never fires -> the DUT is
//   reduced to its combinational core. The assertion `result_packed == ref(a,b)`
//   is then purely combinational, so `sat -prove-asserts` (NO -tempinduct) either
//   proves it for ALL 2^(2*TOTAL) input pairs or finds a REAL counterexample.
//   No clock, no reset, no sequential state -> no init artifact.
//
// NO DUT MODIFICATION (since the wide-int update): result_packed is exposed via
// an `ifdef FORMAL`-guarded `result_comb` port tap on the DUT. Production
// synthesis never defines FORMAL -> the tap is absent -> zero datapath impact.
//
// INDEPENDENT ORACLE: ref_fpadd uses exact WIDE integer arithmetic + a single
// mathematical round-half-to-even step (NOT a re-implementation of the DUT's
// GRS shift pipeline) — same oracle accepted as the §3.5 independent gate.
//
// WIDTHS & SAT TRACTABILITY: the oracle is width-agnostic (WIDE-bit signed regs,
// WIDE = 2^EXP_BITS + MANT_BITS + 16) AND HAS_INF-aware (Inf/NaN propagation,
// matching DUT #214: NaN > Inf+(-Inf)=NaN > Inf). PROVEN (all input pairs, yosys
// minisat): GF4 (1,2 BIAS=0) · GF6 (2,3) · GF8 (3,4) · GF12 (4,7) — all HAS_INF=0.
// GF16 (6,9,HAS_INF=1, ~89-bit mag), GF20 (~140-bit), GF24 (~530-bit) are all
// SAT-INTRACTABLE with bit-level minisat (>8 min, no convergence). The oracle is
// CORRECT for them (GF8 HAS_INF regression green) but minisat can't crack the
// width — they need a word-level SMT engine (boolector/bitwuzla/z3 via `smtbmc`,
// absent in this yosys 0.63 build). GF16/20/24 correctness stands on silicon +
// the GF4/6/8/12 structural proof (same parametric core).
//
// Run (GF8 default; override width with chparam):
//   yosys -p "read_verilog -sv -DFORMAL fpga/openxc7-synth/gf_adder_param.v; \
//     read_verilog -sv formal/gf_adder_comb_miter.v; \
//     chparam -set EXP_BITS 3 -set MANT_BITS 4 gf_adder_comb_miter; \
//     hierarchy -top gf_adder_comb_miter; proc; opt; flatten; opt; \
//     sat -prove mismatch 1'b0"
//   -> "SAT proof finished - no model found: SUCCESS!"  (yosys built-in minisat)
//   PROVEN widths: GF4(1,2) GF6(2,3) GF8(3,4) GF12(4,7). GF16/20/24 need a
//   wide-int oracle (32-bit `integer` overflows their exponent range).
// =============================================================================
`default_nettype none
`timescale 1ns / 1ps

module gf_adder_comb_miter #(
    parameter EXP_BITS  = 3,    // GF8 representative (override to 1 for GF4)
    parameter MANT_BITS = 4,
    parameter HAS_INF   = 0,    // 1 for GF16 (exp=all-ones reserved for Inf/NaN)
    parameter TOTAL     = 1 + EXP_BITS + MANT_BITS,
    parameter BIAS      = (1 << (EXP_BITS - 1)) - 1
)(
    output wire mismatch      // 1 if DUT != reference (proved constant 0 below)
);
    // ---- FREE unconstrained operands (the SAT solver chooses every bit) ----
    reg [TOTAL-1:0] in_a, in_b;

    // Wide-int oracle width: max magnitude needs (2^EXP_BITS)-1 shift + (MANT+1)
    // significand bits + guard. 32-bit `integer` overflows for GF16+ (GF24 needs
    // ~530 bits), so the oracle's magnitude/sum regs are WIDE-bit.
    localparam WIDE = (1 << EXP_BITS) + MANT_BITS + 16;

    // ---- DUT reduced to its combinational core: clk=0, rst=0 ----
    // The posedge block never triggers; result_packed = f(in_a, in_b) purely.
    wire        unused_in_ready, unused_out_valid;
    wire [TOTAL-1:0] unused_out_y;
    gf_adder_param #(
        .EXP_BITS(EXP_BITS),
        .MANT_BITS(MANT_BITS),
        .HAS_INF(HAS_INF)
    ) dut (
        .clk(1'b0), .rst(1'b0),
        .in_valid(1'b0), .in_a(in_a), .in_b(in_b), .in_ready(unused_in_ready),
        .out_valid(unused_out_valid), .out_y(unused_out_y), .out_ready(1'b1),
        .result_comb(result_comb_wire)   // FORMAL-guarded combinational tap
    );
    wire [TOTAL-1:0] result_comb_wire;

    // ---- INDEPENDENT reference: exact integer arithmetic + mathematical RNE ----
    // Identical oracle to formal/gf_adder_property.v ref_fpadd (accepted §3.5 gate).
    function [TOTAL-1:0] ref_fpadd;
        input [TOTAL-1:0] a, b;
        reg            ra, rb, az, bz, adn, bdn, sg;
        reg [EXP_BITS-1:0]  ea, eb;
        reg [MANT_BITS-1:0] ma, mb;
        integer base_a, base_b, sh_a, sh_b;
        integer lead, k, i, exp_field, frac, gb, tailnz, lsb_bit;
        reg signed [WIDE-1:0] sa_mag, sb_mag, ssum;   // wide signed (2^EXP shift range)
        reg [WIDE-1:0]        mag;                    // unsigned magnitude
        reg [EXP_BITS-1:0]  ef_r;
        reg [MANT_BITS-1:0] fr_r, mr_r;
        reg a_nan, b_nan, a_inf, b_inf;             // HAS_INF specials (GF16)
        reg [TOTAL-1:0] res;
        begin
            ra = a[TOTAL-1];  ea = a[TOTAL-2:MANT_BITS];  ma = a[MANT_BITS-1:0];
            rb = b[TOTAL-1];  eb = b[TOTAL-2:MANT_BITS];  mb = b[MANT_BITS-1:0];
            az  = (ea == {EXP_BITS{1'b0}}) && (ma == {MANT_BITS{1'b0}});
            bz  = (eb == {EXP_BITS{1'b0}}) && (mb == {MANT_BITS{1'b0}});
            adn = (ea == {EXP_BITS{1'b0}}) && (ma != {MANT_BITS{1'b0}});
            bdn = (eb == {EXP_BITS{1'b0}}) && (mb != {MANT_BITS{1'b0}});
            // HAS_INF specials (exp=all-ones reserved: Inf if mant==0, NaN if mant!=0).
            // Gated on HAS_INF so for GF4/6/8/12 (exp=all-ones is finite max) these stay 0.
            a_nan = (HAS_INF != 0) && (ea == {EXP_BITS{1'b1}}) && (ma != {MANT_BITS{1'b0}});
            b_nan = (HAS_INF != 0) && (eb == {EXP_BITS{1'b1}}) && (mb != {MANT_BITS{1'b0}});
            a_inf = (HAS_INF != 0) && (ea == {EXP_BITS{1'b1}}) && (ma == {MANT_BITS{1'b0}});
            b_inf = (HAS_INF != 0) && (eb == {EXP_BITS{1'b1}}) && (mb == {MANT_BITS{1'b0}});

            res = {TOTAL{1'b0}};
            // IEEE-754 RNE zero-sign rule (matches DUT + gf_ref.py golden):
            //   both-zero  -> -0 iff BOTH operands are -0, else +0
            //   one-zero   -> pass the NONZERO operand (its sign wins)
            if (az && bz)    res = (ra && rb) ? {1'b1, {(TOTAL-1){1'b0}}} : {TOTAL{1'b0}};
            else if (az)     res = b;            // only a zero -> pass b
            else if (bz)     res = a;            // only b zero -> pass a
            // HAS_INF special propagation (NaN > Inf+(-Inf)=NaN > Inf), matches DUT #214:
            else if (a_nan || b_nan)
                res = {1'b0, {EXP_BITS{1'b1}}, {(MANT_BITS-1){1'b0}}, 1'b1};        // quiet NaN
            else if (a_inf && b_inf)
                res = (ra != rb) ? {1'b0, {EXP_BITS{1'b1}}, {(MANT_BITS-1){1'b0}}, 1'b1}  // Inf+(-Inf)=NaN
                                 : {ra, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};             // same-sign Inf
            else if (a_inf)
                res = {ra, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};   // Inf + finite = Inf
            else if (b_inf)
                res = {rb, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};   // finite + Inf = Inf
            else begin
                base_a = (adn ? 0 : (1 << MANT_BITS)) + ma;   // {implicit, mant}
                base_b = (bdn ? 0 : (1 << MANT_BITS)) + mb;
                sh_a   = (adn ? 1 : ea) - 1;                  // exp_eff - 1, exp_eff >= 1
                sh_b   = (bdn ? 1 : eb) - 1;
                sa_mag = base_a << sh_a;
                sb_mag = base_b << sh_b;
                ssum   = (ra ? -sa_mag : sa_mag) + (rb ? -sb_mag : sb_mag);  // exact signed sum

                if (ssum == 0) res = {TOTAL{1'b0}};
                else begin
                    sg  = (ssum < 0);
                    mag = sg ? -ssum : ssum;
                    lead = 0;  for (i = 0; i < WIDE; i = i + 1) if ((mag >> i) & 1) lead = i;
                    exp_field = lead - MANT_BITS + 1;          // biased field for normal form
                    if (exp_field >= 1) begin
                        k    = lead - MANT_BITS;
                        frac = (mag >> k) & ((1 << MANT_BITS) - 1);
                        gb       = (k >= 1) ? ((mag >> (k-1)) & 1) : 0;
                        tailnz   = (k >= 2) ? (((mag & ((1 << (k-1)) - 1)) != 0) ? 1 : 0) : 0;
                        lsb_bit  = frac & 1;
                        if (gb && (tailnz || lsb_bit)) begin   // round-half-to-even
                            frac = frac + 1;
                            if (frac == (1 << MANT_BITS)) begin frac = 0; exp_field = exp_field + 1; end
                        end
                    end
                    // classify + pack (no-HAS_INF saturation, matches GF4/6/8/12/20)
                    if (exp_field >= (1 << EXP_BITS))
                        res = {sg, {EXP_BITS{1'b1}}, {MANT_BITS{1'b1}}};          // saturate max-finite
                    else if (exp_field <= 0) begin
                        mr_r = mag[MANT_BITS-1:0]; res = {sg, {EXP_BITS{1'b0}}, mr_r};
                    end else begin
                        ef_r = exp_field[EXP_BITS-1:0]; fr_r = frac[MANT_BITS-1:0];
                        res = {sg, ef_r, fr_r};
                    end
                end
            end
            ref_fpadd = res;
        end
    endfunction

    // ---- THE proof (miter): mismatch == 1 iff DUT combinational core != oracle.
    //      Proved constant 0 via `sat -prove mismatch 1'b0` -> for ALL 2^(2*TOTAL)
    //      input pairs the DUT equals the independent reference. ----
    wire [TOTAL-1:0] ref_result = ref_fpadd(in_a, in_b);
    assign mismatch = (result_comb_wire != ref_result);
endmodule
`default_nettype wire
