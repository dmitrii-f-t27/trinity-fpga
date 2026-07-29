# GF+A vector 2: generalization of invariant №18 boundary along the seed/checkpoint/scale axes

**Date:** 2026-07-23. **Hardware:** RunPod NVIDIA RTX PRO 4500 Blackwell (sm_120),
torch 2.11.0+cu128 (auto-reinstall+re-exec with cu124). **Author:** Vasilev (gHashTag).
**Status:** `[measured — GPU]`. **Script:** `webterm_gfplus_v2scale.py`.

The metric is the primary **bits-per-token** (BPT); the Parameter Golf significance
threshold 0.005 BPB = **0.0195 BPT** (coefficient 3.9 bytes/token). Model 9L d=512 VOCAB=1024,
FineWeb sp1024, 27 Linear layers under quantization; Hessian taken from 18/27 (FFN), out_proj → MSE
fallback (a functional-MHA bug from the previous loop). val 24 batches, seed=123 fixed.

## Track A — 2nd checkpoint (seed=42, STEPS=6000) — VALID

Healthy baseline: train loss=3.35, FP32 BPT=**5.26133**.

| bits | MSE | Hessian(FFN) | hybrid(Hess@deep-linear1) | ΔBPT(Hess−MSE) | ΔBPT(hybrid−MSE) |
|---|---|---|---|---|---|
| 4 | 5.26602 | 5.26681 | 5.26221 | **+0.00079** | −0.00381 |
| 6 | 5.26147 | 5.26142 | 5.26122 | **−0.00005** | −0.00024 |
| 8 | 5.26157 | 5.26155 | 5.26133 | **−0.00006** | −0.00024 |

All |ΔBPT| are 1–2 orders of magnitude below the 0.0195 threshold. **Confirms the previous loop
(seed=42, STEPS=3000)** on a different checkpoint: the neutrality of the Hessian choice with
respect to model-BPT — NOT an artifact of a single checkpoint.

A subtlety: at 4 bits Hessian (all FFN) is slightly WORSE than MSE (+0.00079), while the hybrid
(Hessian only in deep linear1) — is the best (−0.00381). This is consistent with
the localization of the SQNR gain in deep FFN (vector 2), but this too is below the threshold.

## Track A — 2nd seed (seed=123, STEPS=3000) — INVALID (collapse)

train loss dropped to **0.0088**, FP32 BPT=**0.00606** → the model overfit into
the memory of the train shard. All ΔBPT=0.00000 ARTIFACTUALLY (there is nothing to quantize on
a degenerate model), NOT a conclusion. Discarded. **Lesson:** on a small set, different seeds
give either a healthy model (42), or a collapse (123) at the same STEPS. The BPT measurement
is valid only at baseline BPT ≥ 1.0. A GUARD was added to the script:
`baseline_valid` in meta + a warning at FP32 BPT < 1.0.

## Track B — scale (NL=12, DMODEL=768) — VALID (OOM fixed)

First run: `torch.OutOfMemoryError` (31.37 GB). Fix:
`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` + auto BATCH budget
(`9*512*48*1024/(NL*D*1024)`) → NL=12/d=768 auto BATCH=24. The repeated run
reached the end: loss=3.89, FP32 BPT=**5.66098**. 36 Linear layers, Hessian taken from 24/36.

| bits | ΔBPT(Hessian−MSE, all FFN) | ΔBPT(hybrid−MSE) |
|---|---|---|
| 4 | −0.00001 | +0.00063 |
| 6 | +0.00000 | +0.00009 |
| 8 | +0.00000 | −0.00001 |

All |ΔBPT| are 3–4 orders of magnitude below the 0.0195 threshold. The neutrality of vector 2 with
respect to model-BPT **holds on the larger model as well**.

## Summary (3 of 3 configurations measured — generalization complete)

| Config | baseline BPT | max |ΔBPT| | Conclusion |
|---|---|---|---|
| 9L/d512, 3000 steps | 3.69 | 0.00022 | neutral |
| 9L/d512, 6000 steps (checkpoint) | 5.26 | 0.00079 | neutral |
| 12L/d768, 3000 steps (scale) | 5.66 | 0.00063 | neutral |
| 9L/d512, seed=123 | 0.006 | — | collapse, discarded |

- **Generalization over the checkpoint `[measured — GPU]`:** the ΔBPT neutrality holds at
  STEPS=6000.
- **Generalization over scale `[measured — GPU]`:** it holds at 12L/d768 too; as the model grows
  the margin compresses further (max |ΔBPT| 0.00079→0.00063).
- **Main conclusion:** the layer-output SQNR (inv. №18) is a surrogate, it does NOT transfer to
  model loss even on a deeper/wider network. NOT an artifact of a single learning point
  along two axes (checkpoint + scale).
- **Caveat on the seed:** seed=123 collapsed → a 2nd HEALTHY seed was not checked;
  e.g. seed=7 STEPS=6000 is needed. A GUARD was added.

## Boundaries (BINDING)
29M PTQ proxy, NOT official Parameter Golf; PTQ ≠ QAT; BPB = BPT/3.9 `[proxy]`
(vocab mismatch: the sp1024 stream is not decoded by the found 8192-BPE); Hessian only
FFN (18/27). The number 5.26 BPT = internal proxy, NOT official trained-from-scratch.
