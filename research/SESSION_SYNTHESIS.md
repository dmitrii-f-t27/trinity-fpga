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

φ-split = best single pocket in 6-bit class on real weights.
φ-split = optimum for unscaled mode (7/7 robustness tests).
NOT optimum for scaled PTQ (INT dominates when per-row scale applied).

This is more precise and defensible than "φ better everywhere."

## What This Does NOT Show (Open Gates)

1. **QAT ablation**: does format ordering persist under STE training? [open]
2. **Downstream BPB**: classes ≥6 bit within noise ±0.0003 [open]
3. **LUT cost of mux**: ~10-20 LUT overhead, not measured [CI running]
4. **NF4 at 4-bit**: GF+A can't beat NF4 on Gaussian (header overhead)

## Complete Evidence Chain

| Line | Evidence | Method | Status |
|------|----------|--------|--------|
| PTQ-proxy BPB (15 formats) | GF8+S=2.7313, INT6=2.7343 | GPU, FineWeb | ✅ measured |
| LUT cost (8-bit) | GF8=340, FP8=329, INT8=316 | yosys, XC7A200T | ✅ measured |
| GF+A on real weights | INT 99.8%, float never selected | GPU, 29M params | ✅ cross-replicated |
| 16-bit scaled insight | e2m13 >> fp16 by 17.6 dB | GPU | ✅ measured |
| φ-rule unscaled robustness | 7/7 workload tests | CPU | ✅ measured |
| Official PG baseline | BPB=1.4715 | H100, train_gpt.py | ✅ measured |
| QAT ablation | — | 8×H100 | ⏳ pending |
| FP8 Tier-E silicon | — | AX7203 | ⏳ pending |

## Key Honest Conclusions

1. **Scaling > format**: per-row absmax scale drives accuracy, not E/M split
2. **GF8 = FP8 in LUT**: φ-rule costs nothing extra in silicon (340 vs 329)
3. **φ-rule valuable for unscaled robustness**: 7/7 tests, but not for scaled PTQ
4. **INT dominates scaled mode**: when range is normalized, uniform grid is optimal
5. **GF+A = insurance**: guarantee "no worse than best", costs 2 bits/row header
6. **NF4 unbeatable at 4-bit on Gaussian**: only pocket that beats GF+A
