# OpenAI Parameter Golf — FULL RESULTS DOSSIER

**Competition**: OpenAI Model Craft Challenge — "Parameter Golf"
**Repo**: https://github.com/openai/parameter-golf
**Status**: Concluded. Leaderboard frozen 2026-05-01.
**Compiled**: 2026-07-16

---

## 1. THE RULES (exact)

| Parameter | Value |
|-----------|-------|
| **Organizer** | OpenAI |
| **Run window** | 2026-03-18 → 2026-04-30 (8 weeks, ~43 days) |
| **Recap posted** | 2026-05-12 ("What Parameter Golf taught us") |
| **Metric** | **BPB (bits per byte)** on held-out FineWeb validation — LOWER IS BETTER |
| **Artifact cap** | **16,000,000 bytes** (decimal MB, NOT 16 MiB / 16,777,216). code bytes + compressed model bytes |
| **Training budget** | **≤ 10 minutes on 8×H100 SXM** |
| **Evaluation budget** | **≤ 10 minutes on 8×H100 SXM** (separate, additional limit) |
| **Hardware** | 8×H100 SXM (final submissions); dev/iteration on cheaper SKUs + Apple Silicon (MLX) |
| **Dataset** | FineWeb (cached `fineweb10B`), 8B training tokens default (80 shards), fixed val = first 50k documents |
| **Tokenizers** | SP1024 (SentencePiece, 1024 BPE vocab), SP4096, SP8192 (vocab 8192), custom (CaseOps) |
| **Prize** | $1,000,000 in Runpod compute credits (OpenAI-sponsored) |
| **Record acceptance** | must beat prior SOTA by **≥ 0.005 nats** at **p < 0.01** (3-seed min) |
| **TTT rule** | test-time training ONLY on val tokens already scored; reset at doc boundary |
| **Eval freedom** | any seq length, sliding window allowed, no val access during training |
| **Self-contained** | no network, no external downloads during eval |

---

## 2. THE HEADLINE NUMBERS

| Metric | Value |
|--------|-------|
| Participants | **1,000+** |
| Total submissions | **2,000+** (README/codeSota say 1,500+ PRs at peak) |
| Open PRs | **1,400+** |
| Repo stars | **5.2k** |
| Forks | **3.3k** |
| Commits | **270** (in main repo) |
| Naive baseline BPB | **1.2244** |
| **FINAL CONFIRMED SOTA (record track)** | **1.05651 BPB** |
| Improvement over baseline | **−0.1679 BPB (−13.7%)** |
| Lowest *claimed* (unverified open PR) | **0.8265 BPB** (SLOT-24 + Pre-Quant AdamW TTT, ndokutovich) |
| Non-record track top | **1.12 BPB** (half of non-record entries beat 1.22 baseline) |

**Confirmed final SOTA**: `val_bpb = 1.05651`, `val_loss = 2.31203 nats`, 3-seed mean (std 0.00036 BPB), max artifact **15,947,490 bytes**.

---

## 3. FULL RECORD-TRACK LEADERBOARD (10min / 16MB)

| # | BPB | Author | PR | Run / Date | Key technique |
|---|-----|--------|----|-----------|---------------| 
| 1 | **1.05651** | codemath3000 | [#2135](https://github.com/openai/parameter-golf/pull/2135) | 2026-05-01 | Calib32 n-gram tilt + AsymLogit + LQER + SmearGate + SparseAttnGate + lrzip. GPTQ_CALIBRATION_BATCHES=32 |
| 2 | 1.05759 | simonbissonnette | #2014 | 2026-04-30 | Progressive context growth→3k + short-doc score-first TTT (AWQ-lite/AsymLogit) |
| 3 | 1.05855 | andrewbaggio1 | #1953 | 2026-04-30 | Long-Context No-Q/V TTT + QK-Gain 5.25 |
| 4 | 1.05943 | alertcat | #1945 | 2026-04-29 | AWQ-lite mixed GPTQ + AsymLogit (V21 v2) |
| 5 | 1.06108 | codemath3000 | #1855 | 2026-04-27 | BOS-fixed SmearGate + LQER + SparseAttnGate + 9-hparam stack |
| 6 | 1.0614 | aquariouseworkman | #1851 | 2026-04-27 | BOS-fix on dexhunter #1797 SmearGate+LQER + phased TTT |
| 7 | 1.0634 | nprime06 | #1787 | 2026-04-23 | Polar Express Newton-Schulz + MIN_LR=0.1 + SparseAttnGate + FusedCE |
| 8 | 1.0645 | dexhunter | #1769 | 2026-04-22 | CaseOps + SmearGate/LoRA-TTT + MLPClip12 |
| 9 | 1.0655 | dexhunter | #1736 | 2026-04-19 | SP8192 + CaseOps + GatedAttn + QuantGate + Loop45 + phased TTT |
| 10 | 1.0678 | romeerp | #1729 | 2026-04-19 | CaseOps tokenizer (lossless caps) + tapered Muon WD |
| 11 | 1.0714 | MarioPaerle | #1667 | 2026-04-16 | SmearGate + attn output gate + depth recurrence + parallel residuals + QK-Gain 5.25 |
| 12 | 1.0719 | dexhunter | #1626 | 2026-04-14 | VarLen attn + fused MLP + multi-phase global SGD TTT + int7 emb + MLR 0.026 |
| 13 | 1.0728 | romeerp | #1610 | 2026-04-13 | VarLenAttn + phasing TTT |
| 14 | 1.0734 | samacqua | #1530 | 2026-04-11 | VarLen FA3 + fused Triton MLP + doc-independent score-first LoRA TTT |
| 15 | 1.0758 | msisovic | #1529 | 2026-04-11 | Parallel residuals + CUTLASS EVT/Triton + legal TTT |
| 16 | 1.0798 | dexhunter | #1514 | 2026-04-09 | SP8192 + Muon 0.97 + score-first TTT |
| 17 | 1.0810 | bigbag | #1493 | 2026-04-09 | SP8192 + 3-layer recurrence + parallel residuals + QK-Gain 5.25 |
| 18 | 1.0822 | aryanbhosale | #1477 | 2026-04-08 | SP8192 + parallel residuals + TTT |
| 19 | 1.0828 | dexhunter | #1413 | 2026-04-06 | SP8192 + QK-Gain 5.0 + score-first TTT |
| 20 | 1.0835 | Robby Sneiderman | #1412 | 2026-04-06 | Parallel residuals + Hessian-aware SDClip + progressive recurrence |
| 21 | 1.0856 | Kevin Clark | #1394 | 2026-04-05 | SP8192 + GPTQ embeddings + loop 4-5 + MuonEq-R + std-GPTQ clip |
| 22 | 1.0897 | aryanbhosale | #1334 | 2026-04-04 | SP4096 + depth recurrence + parallel residuals + MuonEq-R |
| 23 | 1.0912 | dexhunter | #1285 | 2026-04-03 | MuonEq-R + layers 4-5 recurrence + WD=0.090 + all-int6 GPTQ |
| 24 | 1.0979 | Kevin Clark | #1218 | 2026-04-01 | Vocab4096 + 4× MLP + high WD, hash emb, SmearGate, value residuals removed |
| 25 | 1.1063 | Marko Sisovic | #1204 | 2026-03-31 | Parallel residuals + mini depth recurrence (loop 4-5) + AR self-gen GPTQ calib |
| 26 | 1.1099 | newjordan | #1120 | 2026-03-30 | "Rascal": XSA-all + Parallel Muon + coprime loader + Bigram2048/RoPE16 + SWA/late QAT |
| 27 | 1.1122 | dexhunter | #1060 | 2026-03-29 | Coprime multi-shard loader + **Full Hessian GPTQ** + XSA-all + BigramHash(2816×112) |
| 28 | 1.1147 | abaybektursun | #1019 | 2026-03-25 | **Self-Generated GPTQ calibration** (AR) + all-layer XSA |
| 29 | 1.1194 | abaybektursun | #549 | 2026-03-23 | LeakyReLU(0.5)² + legal score-first TTT + Parallel Muon |
| 30 | 1.1228 | signalrush | #374 | 2026-03-22 | GPTQ-lite clip search + EMA + warmdown3500 + QAT@0.15 |
| 31 | 1.1248 | jfprincz | #287 | 2026-03-21 | Partial RoPE (16/64) + layerwise LN scale + EMA + XSA4 |
| 32 | 1.1271 | jfprincz | #198 | 2026-03-20 | XSA last-4 layers + EMA + Int6 MLP3× |
| 33 | 1.1307 | unnir | #198 | 2026-03-20 | Efficient Partial XSA on deepest-3 layers |
| 34 | 1.1428 | thwu1 | — | 2026-03-20 | 10L Int5-MLP + BigramHash(10240) + SWA(0.4) + WD=0.04 |
| 35 | 1.1458 | Raahil Shah | — | 2026-03-20 | Int6 MLP3× + SmearGate + BigramHash + OrthoInit + Muon WD + SWA |
| 36 | 1.1502 | aruniyer | — | 2026-03-19 | 11L MLP3× + int6 QAT + zstd-22 + sliding eval |
| 37 | 1.1556 | aquariouseworkman | — | 2026-03-19 | SmearGate + BigramHash + 3× MLP + int6 STE QAT |
| 38 | 1.1570 | Ciprian-Florin Ifrim | — | 2026-03-24 | **Ternary** {-1,0,+1} 73.7M + bitmask LZMA (see §5) |
| 39 | 1.1586 | yahya010 | — | 2026-03-19 | 10L int6 QAT + zstd-22, MLP1344, Muon 0.99 |
| 40 | 1.1630 | aquariouseworkman | — | 2026-03-19 | Int6 block weights + int8 embeddings + 3× MLP |
| 41 | 1.1748 | notapplica | #60 | 2026-03-19 | Muon WD + spectral embed init + resid mix (combined #50/#42/#39) |
| 42 | 1.1925 | Matthew Li | — | 2026-03-19 | Sliding window eval stride=64 |
| 43 | 1.1928 | samacqua | — | 2026-03-19 | LoRA TTT |
| 44 | 1.2014 | Spokane Way | — | 2026-03-19 | 4k seq length + better hypers |
| 45 | 1.206 | Spokane Way | — | 2026-03-18 | 2k seq length |
| 46 | 1.2147 | Nan Liu | — | 2026-03-18 | 10L mixed int8/int6 |
| 47 | 1.2197 | Renier Velazco | — | 2026-03-18 | FP16 tied embedding + LR/warmdown |
| 48 | **1.2244** | Baseline | — | 2026-03-18 | 9L, dim 512, vocab 1024, tied emb, 4 KV heads |

---

## 4. NON-RECORD / UNLIMITED-COMPUTE LEADERBOARD

| # | BPB | Author | Technique |
|---|-----|--------|-----------|
| 1 | 1.1239 | CiprianFlorin-Ifrim | **1-bit** Binary Asymmetric U-Net FP8 15L 8192BPE YaRN, 106M params, 2h train |
| 2 | 1.1465 | agalimova | MDLM masked diffusion LM (absorbing-mask ELBO), 2×H100 |
| 3 | 1.1467 | mkenney2 | Hymba hybrid Mamba SSM + sliding attn @ 32K ctx |
| 4 | 1.1473 | mradassaad | Mamba-3 hybrid (5 SSM + 2 attn) + SP8192 + AR GPTQ |
| 5 | 1.1898 | ddavidgao | Differential-Gated Attention (Designator/Guided Attn) |
| 6 | 1.1971 | pranavxiyer | Learned adapters on random linear maps (rank-160 LoRA), 12L 3× MLP int6/int8 |
| 7 | 1.2064 | CiprianFlorin-Ifrim | JEPA + Mamba2 "LeWorldModel", INT4/FP8 QAT + Brotli, 37M params |
| 8 | 1.2074 | Will DePue | 4-hour baseline (~quasi-10B from 50B), unlimited compute test |
| 9 | 1.2249 | gowtham0992 | Universal Transformer, 3 blocks×4 loops, 12 effective layers, **4.95 MB artifact** |
| 10 | 1.2266 | sergimichi | LegendreGPT: weights as Legendre poly(layer depth), 24 virtual layers, 15.7 MB |
| 11 | 1.3496 | hardik-bhadani-git | ByteJEPA (no tokenizer) + SIGReg + aux CE head |
| 12 | 1.3595 | DariusFeher | Byte-level H-Net dynamic chunking |
| 13 | 1.3705 | gowtham0992 | Orthogonal random maps + rank-32 LoRA, 30M params, **5.19 MB** |
| 14 | 1.4709 | aarjunsrinivasan | Olmo GDN hybrid long-ctx (8K/16K/32K) |
| 15 | 1.5390 | CiprianFlorin-Ifrim | XNOR-Net binary weights+activations, popcount Triton kernels, 118M params |

---

## 5. THE FINAL SOTA RECORD — FULL BREAKDOWN (PR #2135)

**val_bpb: 1.05651** | **val_loss: 2.31203 nats** | 3-seed mean | max artifact **15,947,490 bytes** | 8×H100 SXM | 600s train / 600s eval

### Per-seed results (final SOTA)

| Seed | Steps | ms/step | Pre-quant BPB | Quant BPB | **Post-TTT BPB** | TTT eval (s) | Artifact (bytes) |
|------|-------|---------|---------------|-----------|------------------|--------------|------------------|
| 0 | 4,997 | 120.0 | 1.06105556 | 1.06939370 | **1.05679341** | 567.1 | 15,942,822 |
| 42 | 5,001 | 119.9 | 1.06026908 | 1.06867913 | **1.05610947** | 540.1 | 15,947,490 |
| 314 | 4,983 | 120.3 | 1.06091124 | 1.06921334 | **1.05662016** | 567.1 | 15,945,305 |
| **Mean** | **4,994** | **120.1** | **1.06074529** | **1.06909539** | **1.05650768** | **558.1** | **15,945,206** |
| Std | — | — | — | — | **0.00035573** | — | — |

### Architecture (PR #2130/#2135 stack)

| Component | Value |
|-----------|-------|
| Layers | 11 |
| d_model | 512 |
| Heads / KV heads | 8 query / 4 KV (GQA) |
| MLP mult | 4× |
| Tokenizer | SP8192 + CaseOps (lossless caps, byte-sidecar accounting) |
| Depth recurrence | layers 3–5 looped (frac=0.35), parallel decoder layer 8+ |
| Gates | BOS-fixed SmearGate (GATE_WINDOW=12), SparseAttnGate (scale=0.5) |
| Optimizer | Muon on matrices (LR=0.028), Adam on emb/scalars (BETA2=0.99) |
| EMA | decay 0.9965 |
| Quantization | **GPTQ int6** matrices + **int7** embeddings + LQER asymmetric rank-4 (GROUP=32, TOP_K=3) |
| Compression | per-group lrzip + brotli |
| Eval context | EVAL_SEQ_LEN=2560, TTT_EVAL_SEQ_LEN=2560 |
| TTT | Quantized phased LoRA (RANK=80, LR=8e-5, WD=2.0), score-first, 1 phase, 2500-doc prefix |
| Logit | AsymLogit Rescale (pos/neg, init 30.0) |
| n-gram tilt | Token-only (TOKEN_ORDER=16, THRESHOLD=0.800, BOOST=2.625) |
| GPTQ calib batches | **32** (the winning lever — was 16 in #2130) |

**Winning delta vs prior #2130**: −0.00019 BPB avg (paired t-test p=0.138; cleared 0.005-nat threshold via 2× margin on nats). Note: PR #2130 was later **excluded for data overlap**; #2135 survived as it was a canonical-data rerun.

---

## 6. THE TERNARY RECORD — FULL BREAKDOWN (#38, Ifrim)

**val_bpb: 1.1570** | 3-seed mean (std 0.0007) | max artifact **15,995,705 bytes** | 8×H100 SXM, **599s**

### Per-seed results

| Seed | Steps | ms/step | Sliding BPB (s16) | val_bpb | RT bpb | Artifact (bytes) |
|------|-------|---------|--------------------|---------|--------|-------------------|
| 42 | 6,530 | 91.7 | **1.1565** | 1.1816 | 1.1837 | 15,993,853 |
| 1337 | 6,520 | 91.9 | 1.1568 | 1.1825 | 1.1839 | 15,995,705 |
| 7 | 6,530 | 91.8 | 1.1578 | 1.1823 | 1.1850 | 15,992,753 |
| **Mean** | **6,527** | **91.8** | **1.1570** | **1.1821** | **1.1842** | **15,994,104** |

### Architecture & techniques (TERNARY)

| Component | Value |
|-----------|-------|
| Layers | 10 |
| d_model | **768** |
| Heads / KV | 8 / 4, head_dim=96 |
| MLP | **4×** (hidden=3072), relu² activation, fused gate+up |
| Params | **73.7M** total (64.9M ternary + 2.5M fp8 + 70KB code) |
| Weight format | **BitNet b1.58 ternary {-1,0,+1}**, ~1.6 bits/param, per-group(128) absmean |
| Artifact | 15.92 MB |
| Optimizer | **NeoMuon**, 3 Newton-Schulz steps, MUON_MOMENTUM=0.95 (warmup 0.85→0.95 over 500 steps) |
| Embedding | Factored tied: 8192×**254** bottleneck |
| Logit | Poly5 softcap (cap=10) + Z-loss 1e-4 |
| Position | YaRN, max_len=2048, ROPE_BASE=5000 |
| Attn | FlashAttention-3 (Hopper), fused QKV |
| Batch tokens | 524,288 (524k) |
| Storage | **FP8 e4m3** for fp_params (~5MB→2.5MB), QAT |
| Compression | **Base-3 + LZMA (preset 9)**, 5 trits/byte → 39% reduction vs int8+zlib |
| Eval | Temperature T=0.90, sliding window stride=16 |

Key finding: **768d/10L beats 512d/25L** (91ms vs 127ms/step → 6,530 vs 4,720 steps in 600s). relu² = −0.024 bpb vs relu.

---

## 7. NUMBER FORMATS USED ACROSS ALL TOP SUBMISSIONS

| Format | Bits/wt | Who used it | Result |
|--------|---------|-------------|--------|
| **FP32** | 32 | (baseline only) | 1.2244 |
| **FP16 / tied embed** | 16 | Renier Velazco, aquariouseworkman (int8 emb) | 1.2197 / 1.1630 |
| **FP8 (e4m3) QAT** | 8 | Ifrim (ternary fp_params) | halves fp storage, only 0.002 bpb RT penalty |
| **INT8** | 8 | early mixed-quant runs | 1.2147 |
| **INT7 (embeddings)** | 7 | dexhunter #1626 | standard for embeddings in top stack |
| **INT6 (GPTQ)** | 6 | dexhunter #1285 (all-int6), jfprincz, aruniyer, Raahil Shah | dominant among top records |
| **INT5 (MLP weights)** | 5 | thwu1 #34 (mixed int5/int6) | ~15% savings vs uniform int6 |
| **INT4 + FP8 QAT** | 4 | Ifrim JEPA non-record | 1.2064 |
| **GPTQ-lite** | ~6 | signalrush #30 (first to use) | 1.1228 |
| **Full Hessian GPTQ** | 6 | dexhunter #27, built on raahilshah #634 | 1.1122 |
| **Self-Gen GPTQ** | 6 | abaybektursun #28 (model generates its own calib data) | 1.1147 |
| **AWQ-lite (mixed)** | 6/8 | alertcat #4, dexhunter | activation-aware salient-group int8 promotion |
| **LQER** (low-rank quant-error) | rank-4 | dexhunter #1797, codemath3000 | asymmetric GROUP=32 TOP_K=3, on top of GPTQ |
| **Ternary {-1,0,1}** | ~1.58 | Ifrim #38 | 1.1570 (73.7M params) |
| **Binary {±1} (1-bit)** | 1 | Ifrim non-record | 1.1239 (106M params, 2h) |
| **XNOR-Net** | ~1 | Ifrim non-record | 1.5390 (118M) |

### Compression layers (on top of number format)
- **zstd-22** (aruniyer, yahya010)
- **LZMA preset 9** (Ifrim, base-3 packing)
- **lrzip + brotli** per-group (codemath3000 #1, #1855)
- **Brotli** (Ifrim JEPA)

---

## 8. ARCHITECTURE & TRICK TAXONOMY

### Architecture
- **Transformer decoder** dominates ALL top records. No MoE, no SSM, no diffusion in record-track top.
- **GQA** (4 KV heads) universal. d_model 512–768. Layers 10–12.
- **Depth recurrence**: loop layers 4-5 (Kevin Clark #21, dexhunter, Ifrim-like). "mini recurrence" first accepted = msisovic #25.
- **Parallel residuals** (two-lane attn/MLP, PARALLEL_RESIDUAL_START=7/8) — appeared ~7× in top records.
- **Universal Transformer** (3 blocks × 4 loops): non-record 4.95MB artifact.
- **LegendreGPT**: 24 virtual layers via Legendre poly of depth, 15.7MB.

### Attention variants
- **XSA (Exclusive / Cross-Sparse Attention)** — efficient partial, GQA-aware grouped views. XSA-all, XSA4 (last 4), Partial XSA (deepest 3). Present in 3 of top 6.
- **VarLen attention** (variable-length FA3) — dexhunter, romeerp.
- **Differential-Gated Attention** — non-record.
- **Partial RoPE (16/64)** + layerwise LN scale — jfprincz.
- **SmearGate** — learned prev-token hidden blend; in most top records.
- **SparseAttnGate** (scale 0.5) — codemath3000 stack.
- **QK-Gain init** 5.0 / 5.25 / 2.25 (QK-GAIN_INIT).
- **YaRN** positional (max 2048, base 5000).
- **FlashAttention-3** universal on H100.

### Optimizers
- **Muon** (matrix optimizer, Newton-Schulz orthogonalization) — near-universal in top records.
- **MuonEq-R**: row-normalizes grads before Newton-Schulz.
- **NeoMuon** (3 NS steps) for ternary STE attenuation.
- **Parallel Muon** (abaybektursun).
- **EMA** decay 0.99–0.9965 (replaced SWA).
- Adam on scalars/embeddings.

### Training tricks
- **Test-Time Training (TTT)** — score-first, per-document LoRA, reset at doc boundaries. LEGAL variant. Powers most top records. RANK 80, LR 8e-5.
- **Phased TTT** / progressive context growth to 3k.
- **Pre-quant TTT** / Pre-Quant AdamW TTT (pending claims, sub-1.0 BPB).
- **Sliding window eval** (stride 16/64) — +~0.025 bpb.
- **Spectral embedding init** (notapplica).
- **Residual-mix scheduling**, **warmdown** (warmdown3500).
- **QAT** (quant-aware training) — late QAT @ 0.15, int6 STE.
- **BigramHash** adjacent-token-pair hash features (10240, 10240, 2816×112, 3072 dims).
- **OrthoInit**, **MLPClip12**, **FusedCE softcap**.
- **Coprime-stride loader** (dexhunter).
- **4× MLP with relu²** (−0.024 bpb free).
- **Factored tied embedding** (8192×254 bottleneck).

### Tokenizer / data tricks
- **CaseOps** (romeerp #1729) — lossless capitalization operator tokens + original-byte BPB sidecar accounting.
- **Self-generated GPTQ calibration** (abaybektursun) — model generates calib text.
- SP8192 vocab became dominant over SP1024.

### Tokenizers used: SP1024 → SP4096 → SP8192 → CaseOps(SP8192)

---

## 9. PENDING UNVERIFIED CLAIMS (open PRs at peak)

| Claimed BPB | Author | Technique |
|-------------|--------|-----------|
| **0.8265** | ndokutovich | SLOT-24 + Pre-Quant AdamW TTT |
| 1.0600 | ndokutovich | Recur345 + Par7 + Pre-Quant TTT |
| 1.0736 | joshkmartinez | Pre-quant TTT + Parallel Residuals |
| 0.979556 | (Lock-In Byte Mixer PR #2138) | **CONFIRMED BPB BUG** (corrected ~1.0671) |

Note: PR #2138 Lock-In Byte Mixer's 0.979556 was invalidated as BPB bug #7 (7th distinct BPB accounting bug found). PR #2140 flagged for target-token n-gram gating violation. PR #727/#758 closed for target-token hash leak. PR #771 closed (train-then-score TTT disallowed by @valerio-oai).

---

## 10. COST / SCALE CONTEXT

- 8×H100 SXM box ≈ **$20/hour** (Runpod).
- $1,000,000 OpenAI/Runpod compute grant pool.
- Top records: ~5,000 steps in 600s @ ~120 ms/step (GPTQ stack); ternary ~6,530 steps @ ~92 ms/step.
- Eval: ~540–567 s (close to the 600 s eval cap).
- Median record-acceptance delta: **0.005 nats** (~0.0025 BPB).
- Inter-run variance: std ~0.0004–0.0007 BPB across seeds.

---

## 11. RELEVANCE TO TRINITY (local context)

From `research/PARAMETER_GOLF_PLAN.md` and `paper.tex` — Trinity's GF16 thesis:

- Trinity IGLA RACE champion on tiny_shakespeare: **BPB 2.5329** (GF16 format) — *different dataset/metric slice, NOT comparable to FineWeb BPB*.
- IGLA controlled 5000-step 8-format study: GF16+SR achieves **lowest validation BPB 0.540**, beating FP32 (0.560). BF16 loses 0.54 BPB (67× worse). MXFP8-E4M3 diverges (BPB 7.08).
- INT7 hybrid gives **BPB 0.265** but fails 5/7 robustness tests.
- 16MB Parameter Golf budget at GF16 (2 B/param) = 8M params; at ternary (2 bits) = 64M params.
- Wave-26 task `gHashTag/trios#645` already ported the PR #2135 **GPTQ_CALIBRATION_BATCHES=32** lever onto Trinity GF16 (CPU-only) via `trios#649`.

**To beat 1.05651 BPB, Trinity would need**: an 8×H100-compatible entry combining GPTQ-int6 + CaseOps + SmearGate + LQER + TTT stack — the GF16 angle (Quire accumulation, φ-anchored LR=0.004) targets lower quant-noise, not a direct format swap.

---

## 12. KEY CITATIONS / SOURCE URLS

- Rules + leaderboard: https://github.com/openai/parameter-golf
- OpenAI recap (2026-05-12): https://openai.com/index/what-parameter-golf-taught-us/
- Live leaderboard: https://parameter-golf.github.io/
- Technique breakdown: https://www.codesota.com/parameter-golf (+ /quantization, /cross-sparse-attention, /test-time-training, /architecture-tricks)
- Final SOTA PR: https://github.com/openai/parameter-golf/pull/2135
- Ternary record: `records/track_10min_16mb/2026-03-24_74M_Ternary_UNet_FP8_10L_8192BPE_YaRN_NeoMuon/`
- Baseline: `records/track_10min_16mb/2026-03-17_NaiveBaseline/`
- Inspiration: NanoGPT Speedrun (KellerJordan/modded-nanogpt), target 3.28 FineWeb val loss ASAP.
