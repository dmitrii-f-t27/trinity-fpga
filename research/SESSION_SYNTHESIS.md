# Session Synthesis — Four Lines of Evidence
**Date:** 2026-07-18  
**Commits:** 20+ on main  
**Status:** All CPU/GPU experiments exhausted; QAT ablation pending 8×H100

---

## 1. Scientific Contribution: Format Selection Procedure

GF+A = working prototype of the "optimizer layer" above the format catalog.
Our 83-format catalog with conformance vectors transforms from collection
to search space. No competitor covers this niche (Tekum, b-posit, FlexInt
all propose single formats; we propose the selection procedure).

**Material for paper3/ВАК.**

## 2. Hardware Directive: Narrow-Exponent Decoder

Per-row scaling saturates optimal exponent at e2–e3 for all distribution
classes. Wide exponents (e4m3, fp16, bf16) waste bits in scaled mode.

**Engineering implication:** weight decoder can be narrow-exponent + cheap.
GF+A cell = 4 pockets + mux = candidate for new FPGA compute cell.
LUT cost being measured in CI ablation.

## 3. Quantization Practice: Insurance Container

GF+A guarantee: "no worse than best pocket" on ANY data, at 2 bits/row header.
Margin on uniform weights: +0.01–0.08 dB (insurance, not breakthrough).
Margin on heterogeneous data: substantial (testA/C show larger gaps).

## 4. φ-Rule Niche: Corrected

φ-split = best single pocket in 6-bit class on real weights AND dominant
pocket inside GF+A (89% of rows). φ-split = optimum for unscaled mode
(7/7 robustness tests, agent harness). NOT optimum for scaled PTQ at
≥8 bit — but the winner there is the narrow-exponent FLOAT e2 (e2m5,
e2m13), NOT INT. «INT dominates» was a v1-bug artifact (retracted,
see GFPLUS_REAL_WEIGHTS_RESULT.json retraction_note).

This is more precise and defensible than "φ better everywhere."

## What This Does NOT Show (Open Gates)

1. **QAT ablation**: CLOSED [measured — GPU, 3 seeds]. PTQ↔QAT inversion confirmed.
   PTQ best (e2m5, 43.1 dB SQNR) = QAT worst (+0.27 BPB).
   FP8S (e4m3 scaled) = indistinguishable from FP32 in QAT (Δ=+0.0001).
   Mechanism: narrow exponent restricts weight dynamics under STE.
   See research/QAT_ABLATION_RESULTS.json.
2. **Downstream BPB**: classes ≥6 bit within noise ±0.0003 [open]
3. **LUT cost of mux**: ~10-20 LUT overhead, not measured [CI running]
4. **NF4 at 4-bit**: GF+A rides on NF4 (95% of rows), margin +0.01 dB —
   the 2-bit/row header is not paid back vs pure NF4 on this model

## Complete Evidence Chain

| Line | Evidence | Method | Status |
|------|----------|--------|--------|
| PTQ-proxy BPB (15 formats) | GF8+S=2.7313, INT6=2.7343 | GPU, FineWeb | ✅ measured |
| LUT cost (8-bit) | GF8=340, FP8=329, INT8=316 | yosys, XC7A200T | ✅ measured |
| GF+A on real weights | ≥ best single in all 4 classes (+0.01…+0.08 dB); pockets: nf4 95% (4b), φ-e2m3 89% (6b), e2m5 87% (8b), int8 only 5.9% | GPU, 29M params, 2 impls | ✅ cross-replicated (v2) |
| 16-bit scaled insight | e2m13 >> fp16 by 17.6 dB | GPU | ✅ measured |
| φ-rule unscaled robustness | 7/7 workload tests | CPU | ✅ measured |
| Official PG baseline | BPB=1.4715 | H100, train_gpt.py | ✅ measured |
| QAT ablation | FP8S=2.8280 (Δ=+0.0001), GF8S=3.0474 (Δ=+0.22) | GPU, 3 seeds | ✅ CLOSED |
| FP8 Tier-E silicon | — | AX7203 | ⏳ pending |

## Key Honest Conclusions

1. **Scale is necessary, but split still matters**: per-row scale is the
   prerequisite (unscaled GF8 = BAD), yet WITHIN the scaled 8-bit class the
   split spans 43.1 (e2m5) → 31.6 (e4m3) → 25.6 dB (e5m2) — an 11.5 dB
   range. «Scaling, not format, drives quality» is TOO STRONG; honest form:
   scale first, then narrow-exponent split second.
2. **GF8 ≈ FP8 in LUT (yosys estimate)**: 340 vs 329 core-only sums from the
   local-agent table; apples-to-apples CI (identical wrapper, ADD/MUL
   separately) pending — gf8_mul cell not routed yet.
3. **φ-rule valuable for unscaled robustness** (7/7 agent tests) and best
   single 6-bit pocket in scaled mode; loses to e2 at ≥8 bit scaled.
4. **Narrow-exponent floats win scaled mode ≥6 bit** (e2m3/e2m5/e2m13);
   INT is a minority pocket (5.9% at 8-bit). Note grid identities:
   e1m2/b0≡int4, e1m4/b0≡int6, e1m6/b0≡int8 — equal numbers in tables
   for these triples are format identities, not bugs.
5. **GF+A = insurance**: guarantee "no worse than best pocket", costs
   2 bits/row header; margin on uniform weights does not repay the header.
6. **NF4 strongest 4-bit pocket on Gaussian-like weights**: GF+A ≥ it by
   construction (+0.01 dB) and selects it for 95% of rows.
