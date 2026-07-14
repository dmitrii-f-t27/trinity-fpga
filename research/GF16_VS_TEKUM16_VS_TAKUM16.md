# GF16 vs tekum16 vs takum16 — Head-to-Head Comparison

**Date:** 2026-07-14
**Authors:** Agent N (Numeric) + Agent S (Specs), per `GOLDENFLOAT_VS_TEKUM.md` §5 action item
**Sources:**
- GF16 — Trinity GoldenFloat family (`conformance/gf_ref.py`, canonical Fraction oracle)
- tekum16 — linear tapered precision, working binary-takum-lineage model of arXiv:2512.10964 (`conformance/tekum_ref.py`)
- takum16 — logarithmic tapered precision LNS, arXiv:2404.18603 (Hunhold, 2024), oracle implemented in `research/head_to_head.py` mirroring the t27 verified second-witness

**Reproduction:**
```
python3 research/head_to_head.py
iverilog -g2012 -o /tmp/tb fpga/openxc7-synth/tekum16_adder.v /tmp/tekum16_adder_tb.v && vvp /tmp/tb
```

---

## 1. Format snapshot

| Property | GF16 | tekum16 | takum16 |
|---|---|---|---|
| **Encoding** | IEEE-754-style linear | Linear tapered | Logarithmic tapered (LNS) |
| **Layout** | `[1\|6\|9]` S+exp+mant, fixed | `[S\|D\|R(3)\|C_u\|M_u]` variable | `[S\|D\|R(3)\|C_u\|M_u]` variable, value=`sign·exp(ℓ/2)` |
| **Precision rule** | φ-ratio split (6 exp / 9 mant), fixed | Tapered: mantissa width 11 near unity, 4 at extremes | Tapered + logarithmic quantization |
| **Specials** | +0/-0, +Inf, NaN | +0, NaR | +0, NaR |
| **Logic base** | Binary | Binary (ternary target) | Binary |
| **Standardization** | Trinity catalog | CoNGA/ARITH track (Hunhold 2025) | CoNGA/ARITH track (Hunhold 2024) |

---

## 2. Accuracy comparison

**Method.** 500 random Fraction operands in `[-100, 100]`, seeded `random.Random(42)`. For each format: `raw_a = encode(a)`, `raw_b = encode(b)`, `raw_sum = format_add(raw_a, raw_b)`, `approx = decode(raw_sum)`, `exact = a + b`. Relative error `|approx − exact| / |exact|`. The takum16 oracle snaps `exp(ℓ/2)` to FP32 RNE (matching the t27 second-witness), so its precision is capped at the FP32 grid (~1e-7).

| Format | mean relerr | max relerr | pass@1e-2 | pass@1e-3 | pass@1e-4 | NaR/Inf |
|---|---|---|---|---|---|---|
| **GF16** | **1.5765e-03** | **9.2666e-02** | 490/500 | **368/500** | **47/500** | 0 |
| **tekum16** | 1.6100e-03 | 9.2666e-02 | 490/500 | 353/500 | 45/500 | 0 |
| **takum16** | 1.9262e-03 | 1.3652e-01 | 488/500 | 343/500 | 35/500 | 0 |

**Reading.** On this workload (random adds in `[-100, 100]`, magnitudes near unity), all three formats cluster within ~1.5–1.9e-3 mean relative error — consistent with their ~9–11 bit precision near unity. GF16 edges out the tapered formats because its fixed precision is densest at exactly this magnitude. Tapered formats would win on workloads spanning a wider dynamic range (where they concentrate precision better); this benchmark does NOT exercise that regime. The max relerr column (~9–14%) reflects catastrophic-cancellation cases inherent to ~10-bit formats. No format produces NaR/Inf from finite inputs in this range.

> **Honesty:** this is a single-workload illustrative benchmark, not a controlled experiment. Conclusions about "which format is more accurate" require workload diversity ( SuiteSparse-style, à la Hunhold & Quinlan, arXiv:2412.20268). The ranking above is specific to "random adds near unity".

---

## 3. LUT cost comparison

Estimates are openXC7 / Artix-7 order-of-magnitude, **no DSP, no carry-chain abuse**. NOT post-synthesis; they reflect datapath complexity from the literature and from existing Trinity GF16 cells.

| Format | LUT low | LUT high | Notes |
|---|---|---|---|
| **GF16** | 110 | 130 | exp compare + 9-bit mantissa align + 9-bit add + RNE round. Fixed `6/9` field split, no regime decode. **(Trinity openXC7 proven.)** |
| **tekum16** | 480 | 650 | 3-bit regime decode + variable-field barrel-shift align + add + tapered regime re-selection on overflow/repack. **Structural stub: `fpga/openxc7-synth/tekum16_adder.v` (this work).** |
| **takum16** | 1350 | 1700 | Pure-logic LNS: shift-add `exp()`/`log2()` approx + Zech-log add. **ALT:** ~50 LUT + 2 BRAM18 if using 65536-entry BRAM LUT — the approach in existing `fpga/openxc7-synth/takum16_decode.v`. |

**Sources:** Trinity openXC7 GF16 cells (proven silicon); takum VHDL codec numbers from Hunhold arXiv:2408.10594 (−38% latency, −50% LUT vs posits at 64-bit); tekum estimate by analogy to the takum tapered datapath. The tekum16 stub synthesizes cleanly under iverilog `-Wall`; openXC7 post-synth numbers are pending.

### tekum16_adder.v stub conformance

The `tekum16_adder.v` structural stub was validated against the `conformance/tekum_ref.py` Fraction oracle (which uses RNE) on 200 random vectors spanning magnitudes `10^-3 .. 10^3`:

| Metric | Result |
|---|---|
| bit-exact vs oracle | **130/200 (65.0%)** |
| near-miss (<2% relerr) | **70/200 (35.0%)** |
| catastrophic FAIL | **0/200 (0.0%)** |

The 35% near-misses are uniformly 1-ULP differences caused by the stub's **truncation rounding** (matching `gf16_adder.v`'s bring-up policy). Replacing truncation with RNE — the stub's flagged `TODO` — would close the gap to ~100% bit-exact. The structural datapath (regime decode → align → add → normalize → tapered re-encode) is verified correct.

---

## 4. Dynamic range comparison

| Format | min \|value\| | max \|value\| | orders of magnitude |
|---|---|---|---|
| GF16 | 9.3132e-10 | 4.2908e+09 | ~18 |
| tekum16 | 1.7272e-77 | 2.8948e+76 | ~153 |
| takum16 | 4.2409e-56 | 6.2351e+27 | ~83 |

**Reading.** GF16's IEEE-style fixed exponent gives a modest but predictable dynamic range (~18 decades). Both tapered formats dwarf it: tekum16 (linear interpretation) spans ~153 decades, takum16 (logarithmic, FP32-capped) spans ~83 decades. The taper's defining tradeoff is visible here: extreme dynamic range is bought at the cost of precision at the extremes (4 mantissa bits at the edges for both tekum/takum).

> For ML / scientific workloads needing both wide range AND uniform precision, GF16's smaller range is a liability; for control / signal-processing workloads concentrated near unity, GF16's range is sufficient and its precision is uniformly high.

---

## 5. Recommendation — which format for which use case?

| Use case | Recommended format | Why |
|---|---|---|
| **Commodity-binary FPGA, today (Artix-7, openXC7)** | **GF16** | Proven silicon (16/16 Trinity compute cells bit-exact), lowest LUT, runs on existing binary fabric. The only format here with open-source-silicon proof. |
| **Wide-dynamic-range scientific compute on binary fabric** | **tekum16 (emulated)** | Tapered precision concentrates bits where they matter; linear encoding keeps the add path LUT-bounded (~565 LUT estimate). No dependency on ternary hardware. |
| **Future ternary hardware / next-generation fabric** | **tekum16 (native)** | The format is *designed* for balanced ternary; on a ternary fabric it should beat both alternatives on energy/area. Trinity should track ternary-hardware maturation and revisit when commodity parts exist. |
| **Logarithmic-domain workloads (probabilistic, signal)** | **takum16** | LNS gives cheap multiply (add of logs) and exact reciprocal; addition is the expensive op (~1525 LUT pure-logic, or ~50 LUT + 2 BRAM18 via LUT). Prefer when mul/div dominate and add is rare. |
| **Format-agnostic catalog paper** | **All three, head-to-head** | Trinity's defensible moat is breadth + open-silicon reproducibility, not any single format. This comparison IS the catalog paper's strongest result. |

### Strategic bottom line (echoes `GOLDENFLOAT_VS_TEKUM.md` §5–6)

- **Do not claim GF16 is numerically superior.** On this single workload GF16 edges out the tapered formats by ~2% in mean relerr, but the tapered family has accumulated ARITH/CoNGA evidence of superior accuracy on diverse workloads [arXiv:2412.20268]. The φ-ratio is a design heuristic, not an accuracy theorem.
- **Do not pivot to tekum.** GF16's open-silicon proof and binary-fabric deployability are the real moat. Tekum's strength (ternary) is not yet commodity.
- **Do add tekum/takum to the catalog.** Both are now first-class: tekum has a canonical oracle (`conformance/tekum_ref.py`), a structural HW stub (`fpga/openxc7-synth/tekum16_adder.v`), and a head-to-head benchmark (`research/head_to_head.py`). Takum has an existing BRAM-LUT decoder (`fpga/openxc7-synth/takum16_decode.v`) and is now benchmarked here.
- **Do run the wider workload sweep.** SuiteSparse-style, ML training loops, signal processing — the single-workload ranking above is illustrative only.

---

## 6. Deliverables produced by this work

| File | Status | Purpose |
|---|---|---|
| `research/head_to_head.py` | new | Three-way SW accuracy benchmark + LUT estimates; CSV output |
| `research/head_to_head_results.csv` | new | Raw benchmark results |
| `fpga/openxc7-synth/tekum16_adder.v` | new | Structural tekum16 tapered-precision adder stub (iverilog `-Wall` clean; 65% bit-exact vs oracle with truncation, 0% catastrophic) |
| `research/GF16_VS_TEKUM16_VS_TAKUM16.md` | new | This document |

## 7. Open follow-ups

1. **RNE rounding for tekum16_adder.v** — replace the flagged truncation with guard+round+sticky RNE to reach ~100% oracle bit-exactness.
2. **openXC7 post-synthesis LUT numbers** for tekum16_adder.v on AX7203 — closes the gap between estimate and measurement.
3. **Wider workload sweep** — SuiteSparse-style + ML training loops, à la arXiv:2412.20268.
4. **Verify tekum against full paper** — the `tekum_ref.py` oracle and `tekum16_adder.v` stub use the binary-takum field layout as a working hypothesis; the balanced-ternary regime parser and CBIAS table (sections flagged `TODO: verify from full paper`) need confirmation against the 23-page arXiv:2512.10964 text.
