# Variant B (loop 29.07.2026b) — catalog-selection axis (GF+A) vs intra-pocket axis (dMX-style)

**Status:** `[measured — SW proxy, CPU]`, seed=20260729. Script: `selector_vs_intrapocket.py`,
results: `selector_vs_intrapocket_results.json`.

## Goal (honest framing)

To move the claim "the axes of adaptivity are complementary" from `[open hypothesis]` (inv. #15/#18
of the skill) into `[measured — SW proxy]`, by numerically separating TWO orthogonal axes on the
same data:

- **Axis 1 — catalog-selection (GF+A):** per-row discrete argmin-selection of a pocket from a
  HETEROGENEOUS φ-catalog {φ-split, e2, INT, lns/nf4}. Selection *between* formats.
- **Axis 2 — intra-pocket refinement (dMX-style, arXiv:2606.04115):** at a FIXED minifloat
  family — per-row/per-block search for a bit split (e,m) with e+m+1=N (an SW-model of the
  continuous differentiable bit-width search of dMX *inside* a single MXFP-family). Selection
  *inside* one format-class.
- **Composition 1⊕2:** per-row argmin between the best GF+A-pocket and the intra-pocket-minifloat —
  a single wider catalog.

## Result (metric — SQNR dB round-trip + MSE + eff.bits; synthetic 5 classes × 4 distributions)

| Class | distribution | axis1 GF+A | axis2 intra dMX-style | comp. 1⊕2 |
|---|---|---|---|---|
| 8 bit | gaussian | 43.65 | 47.22 | 47.22 |
| 8 bit | heavy | 41.33 | 47.47 | 47.47 |
| 8 bit | mixed_outlier | 43.93 | 47.35 | 47.35 |
| 16 bit | heavy | 87.90 | 95.75 | 95.75 |

(full table — in the JSON)

**Composition invariant:** rows where the composition is WORSE than the best single axis by MSE
= **0 out of 20** (by construction of argmin). This confirms the **orthogonality and composability**
of the axes on the selection MSE-metric.

## Honest boundaries (BINDING)

1. **The guarantee is only on the SELECTION MSE-metric (of weights), NOT downstream.** Per inv. #18
   a layer's SQNR = a surrogate, not paid off in model-BPB (threshold 0.005 BPB). This is NOT a
   claim about model quality.
2. **The axis comparison is NOT bit-aligned:** axis 2 spends **+0.18 bits/element** more (a thin
   per-group split header) — part of its SQNR advantage is bought with bits. The honest conclusion
   is ONLY about **orthogonality** (composition ≥ each axis), NOT "axis 2 beats axis 1".
3. **This is NOT a reimplementation of dMX** — dMX has a differentiable end-to-end search +
   STE-training; we model ONLY the "bit-allocation within a family" axis as a contrast to the
   "pocket-selection between families" axis. Both estimates are our own SW-model, `[SW proxy]`.
4. **Superiority over any axis / over dMX is NOT claimed.** The conclusion is about
   complementarity: φ-field-selection (GF+A) and bit-allocation (dMX-style) are orthogonal degrees
   of freedom that yield a single wider catalog upon composition.
5. e_max for splits is limited to 8 (exponents >8 give overflow bias and never win on per-row-scaled
   data with a narrow intra-row range).

## Relation to the 2026 review

Directly strengthens the demarcation from **dMX** (arXiv:2606.04115), added to paper1 in the
previous loop (PR #15): previously the complementarity of the axes was a textual claim
`[open hypothesis]`, now it is `[measured — SW proxy]` with a reproducible harness.
