# GF+ line — φ-catalog of pockets + adaptive GF+A container

Status: `[measured — SW proxy, CPU]`, seed=20260718. PTQ of weights, per-row scale. NOT QAT, NOT downstream of large models.

## Main result

A fixed split that "beats everyone at everything" is impossible — empirically confirmed
by an exhaustive sweep of splits (testA): on gaussian/heavy tails e2 wins, on rows with
outliers e3 wins, on uniform INT. The honest form of "+" is **GF+A: an adaptive container**:

- per-row absmax scale (fp16) — like GF8+S;
- per-row pocket selection from the φ-catalog: `{φ-split, e2, e3, INT-grid}` (class 4: `{e1m2, e2m1, INT4, NF4}`);
- header 2 bits/row; overhead (2+16)/C bits per element — at C=2048 this is 0.009 bpe.

**By construction** the per-row MSE of GF+A ≤ MSE of any single pocket in the set.
Measurement (testC): GF+A is the best or equal to the best in all 20 cells
(5 classes × 4 distributions) and on real weights of a micro-LM.

## Key insight about the φ-rule

With per-row scaling, the intra-row dynamic range does NOT grow with bit-width → the
optimal exponent saturates at e2–e3 for all classes. The φ-proportion
`e=round((N−1)/φ²)` is optimal for the UNSCALED regime (the format itself covers the
global range); in scaled mode the φ-catalog remains a SPACE of candidates,
and the data makes the choice (= "the best format is the selection procedure").

Coincidences: class 6 — φ yields e2m3 = winner for gaussian/heavy tails; class 8 — φ yields
e3m4 = winner for outlier rows (this also explains the victory of GF8+S on the 29M pod checkpoint).

## Files

- `gfplus_quant.py` — generic minifloat (any e/m/bias, RNE, denormals, fn), INT, NF4, scaled-wrapper.
- `gfplus_adaptive.py` — GF+A (pockets, argmin per-row, header).
- `testA_sweep.py` — exhaustive sweep of splits across classes 4/6/8/12/16 on 4 distributions.
- `testB_realweights.py` — PTQ ΔBPB on real weights of a micro-LM (char-LM, tinyshakespeare).
- `testC_adaptive.py` — GF+A vs all fixed arms (synthetic + real weights).
- `gfplus_pod_benchmark.py` — SELF-CONTAINED script for the pod:
  `python3 gfplus_pod_benchmark.py /workspace/model.pt` (any state_dict) or `--synthetic`.

## Honest boundaries (BINDING)

1. The GF+A guarantee is on the SELECTION metric (per-row MSE). Downstream BPB correlates
   but is not identical: on 4-bit real weights pure NF4 gave ΔBPB +0.0032 vs GF+A +0.0035.
2. All ΔBPB of classes ≥6 bits on the micro-LM are within ±0.0003 — they cannot be ranked by it,
   SQNR ranks them. Parameter Golf significance threshold = 0.005.
3. The GF+A decoder = 4 pockets + a multiplexer → more expensive than a single format in hardware;
   the LUT cost has not been measured `[open hypothesis]`.
4. QAT behavior of GF+A has not been verified; PTQ ≠ QAT.
