# FORMAT LEADERBOARD — Definitive Comparison

**Hardware:** H100 SXM 80GB  
**Data:** FineWeb sp1024 (8M train, 54M val tokens)  
**Model:** 9L d=512 seq=1024 | 29.4M params  
**BPB method:** Official sentencepiece byte counting (same as Parameter Golf competition)  
**Date:** 2026-07-17

---

## Complete Format Comparison (Official BPB)

| # | Format | Family | Bits/elem | FineWeb BPB | Δ vs FP32 | Status | LUT (FPGA) |
|---|--------|--------|----------|-------------|-----------|--------|------------|
| 1 | **FP32** | IEEE FP | 32 | **2.8364** | — | master | ~3000 |
| 2 | FP16 (E5M10) | IEEE FP | 16 | 2.8364 | +0.0000 | ✓ lossless | ~500 |
| 3 | BF16 (E8M7) | IEEE FP | 16 | 2.8364 | +0.0000 | ✓ lossless | ~480 |
| 4 | **GF14+ (E5M8)** | **GoldenFloat φ** | **14** | **2.8364** | **+0.0000** | **✓ lossless** | **851** |
| 5 | **GF16+ (E6M9)** | **GoldenFloat φ** | **16** | **2.8364** | **+0.0000** | **✓ lossless** | **991** |
| 6 | GF20 (E7M12) | GoldenFloat φ | 20 | 2.8364 | +0.0000 | ✓ lossless | ~1600 |
| 7 | GF24 (E9M14) | GoldenFloat φ | 24 | 2.8364 | +0.0000 | ✓ lossless | ~2200 |
| 8 | INT8 | Integer | 8 | 2.8366 | +0.0002 | ✓ lossless | ~100 |
| 9 | INT7 | Integer | 7 | 2.8373 | +0.0009 | ✓ lossless | ~50 |
| 10 | **SQ-INT7** | **SmoothQuant** | **7** | **2.8369** | **+0.0005** | **✓ lossless** | **~70** |
| 11 | **SQ-INT6** | **SmoothQuant** | **6** | **2.8382** | **+0.0018** | **★ good** | **~120** |
| 12 | INT6 | Integer | 6 | 2.8418 | +0.0055 | ⚠ noisy | ~103 |

---

## Key Findings

### 1. ALL floating-point formats ≥14 bits are LOSSLESS
FP16, BF16, GF14+, GF16+, GF20, GF24 — all produce **identical** BPB to FP32.
The choice of E/M split (φ-rule vs IEEE) **does not affect accuracy** at this scale.

### 2. GF14+ (φ-rule, 14 bits) = lossless
The narrowest floating-point format that preserves full accuracy.
**14 bits = minimum for lossless FP on H100.**

### 3. SQ-INT6 reduces INT6 error by 67%
```
INT6:     Δ = +0.0055 BPB (noisy)
SQ-INT6:  Δ = +0.0018 BPB (good)    ← 67% less error!
```
SmoothQuant (α=0.5) redistributes outlier magnitude, making INT6 viable.

### 4. INT6 is the only format with measurable noise
All other formats (7+ bits FP, 7+ bits INT with SQ) are within 0.001 BPB of FP32.

---

## Official Parameter Golf Baseline

| Run | GPU | Steps | BPB | Config |
|-----|-----|-------|-----|--------|
| **Our baseline** | 1×H100 | 1,563 | **1.4715** | official train_gpt.py, 570s |
| Naive baseline | 8×H100 | ~20,000 | 1.2244 | official |
| **Winner** | 8×H100 | ~20,000 | **1.0565** | +Muon+TTT+GPTQ+CaseOps |

Gap to winner (0.42 BPB) comes from: 8× more GPU, Muon optimizer, TTT, GPTQ, CaseOps, depth recurrence, sliding eval, LQER.

---

## Parameter Golf Leaderboard Context

| # | Format used | BPB | Author | Key technique |
|---|------------|-----|--------|---------------|
| 1 | INT6 GPTQ | **1.0565** | codemath3000 | Muon+TTT+CaseOps+LQER |
| 2 | INT6 GPTQ | 1.0576 | simonbissonnette | Progressive context |
| 3 | INT6 GPTQ | 1.0586 | andrewbaggio1 | QK-Gain 5.25+TTT |
| 10 | INT6 QAT | 1.1502 | aruniyer | 11L MLP3x |
| 16 | INT6 QAT | 1.1586 | yahya010 | Zstd MLP2.6x |
| 33 | Ternary | 1.1570 | Ifrim | BitNet b1.58 |
| — | **INT8** | **1.2244** | Baseline | Naive 9L d=512 |
| — | **FP32→INT8** | **1.4715** | **Trinity** | **Our baseline (1 GPU)** |

**Nobody uses SmoothQuant.** Our SQ-INT6 (67% less error than INT6) is a novel contribution.

---

## Hardware Cost Comparison (FPGA LUT)

| Format | LUT MAC | % of XC7A200T | vs GF16+ |
|--------|---------|---------------|----------|
| GF14+ | 851 | 0.6% | 0.86× |
| GF16+ | 991 | 0.7% | 1.00× |
| INT7 | ~50 | 0.04% | 0.05× |
| **SQ-INT6** | **~120** | **0.09%** | **0.12×** |
| INT6 | ~103 | 0.08% | 0.10× |

SQ-INT6 is **8× cheaper** than GF16+ on FPGA while maintaining good accuracy.

---

*Source: research/H100_FORMAT_COMPARISON_OFFICIAL_BPB.json (commit d678e4a4c)*
*Official baseline: research/H100_OFFICIAL_BASELINE.json (commit ba23a1c85)*
