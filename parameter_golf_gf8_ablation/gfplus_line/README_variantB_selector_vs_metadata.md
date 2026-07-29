# Variant B — catalog-selection (GF+A) vs metadata-augmentation (M²XFP-style)

`[measured — SW proxy, CPU]`, seed=20260730.
Script: `format_selector_vs_metadata.py` · data: `format_selector_vs_metadata_results.json`.

## Framing (honest)

Two DIFFERENT axes of adaptivity on the SAME data, comparable bit-budget:

- **Axis 1 — catalog-selection (GF+A):** per-row argmin-selection of a **pocket** from a
  φ-catalog of **DIFFERENT** formats `{φ-split, e2, INT, lns/nf4}` + per-row e8m0-scale.
  Selection granularity = **row**. (SSOT — `gfplus_a_v2`, not duplicated.)
- **Axis 2 — metadata-augmentation (M²XFP-style, arXiv:2601.19213):** we fix
  **ONE** format-pocket (microscale-base `e2`), then for each **subgroup**
  (16 elements) we fit a small flex-metadata — an order shift `b∈{-1,0,+1}`,
  `b*=argmin_b Σ‖q_b−w‖²` (like `b*` in the M²XFP abstract). The format does NOT change.
  Selection granularity = **subgroup**.

## Result (20 cells: 5 bit-widths × 4 distributions)

Winner by SQNR (round-trip quantize→dequantize):

| Distribution | Winner | Typical ΔSQNR (catalog − metadata) |
|---|---|---|
| `uniform`       | **catalog-select (GF+A)** | +2.9 … +3.2 dB (all 5 bit-widths) |
| `gaussian`      | metadata-refine (M²XFP)   | −1.4 … −1.5 dB |
| `heavy` (t, ν=2.5) | metadata-refine (M²XFP) | −4.7 … −6.8 dB |
| `mixed_outlier` | metadata-refine (M²XFP)   | −0.4 … −1.5 dB |

Total: catalog 5 wins / metadata 15 wins out of 20 — **but this is NOT a ranking**, it is a
regime map: the winner **deterministically** depends on the statistics of the data.

## Conclusion (BINDING — what can and CANNOT be claimed)

- **The axes are ORTHOGONAL and COMPLEMENTARY, not competitors for a cell.**
  On uniform data the *format* choice wins (the INT-pocket fits exactly, subgroup metadata only
  adds overhead). On gaussian/heavy tails/outliers the *refinement of metadata inside the format*
  wins (the subgroup shift catches intra-row non-uniformity that a single row-pocket misses). This
  is direct numerical confirmation of "no free lunch" and of the paper's position: M²XFP and GF+A
  work at DIFFERENT levels (selection *between* formats vs refinement *inside* a format) → they can
  be **composed**, rather than choosing one.
- **Superiority of EITHER axis is NOT claimed.** Each axis's guarantee holds only on its own
  selection MSE-metric; **downstream was NOT measured** (inv. #15/#18: SQNR ≠ model loss).

## Honesty boundaries (BINDING)

1. This is **NOT a reimplementation of M²XFP** — we do not have their HW-co-design/training. We
   model ONLY the "metadata-refinement inside a single format" axis as a contrast. Both estimates
   are our own SW-model, `[SW proxy]`.
2. The comparison is **NOT strictly iso-bit:** the metadata-axis carries +0.117 bits/element of
   overhead (2 bits of flex-metadata per subgroup of 16 + a shared e8m0-scale). Part of the
   metadata gain on tails is payment by these bits. When the overhead is aligned (K↑ or b∈{0,1})
   the margin will shrink — not verified.
3. The different **selection granularity** (row vs subgroup) is the fundamental cause of the
   divergence, not the "quality" of an axis. Composition (GF+A-pocket + subgroup metadata inside
   it) is an `[open hypothesis]`, not measured end-to-end in this script.
4. Synthetic + (if available) real weights of a micro-LM; 1 seed. Downstream/BPB — out of scope.
