# FORMAT LEADERBOARD — Definitive Comparison (15 formats)

**Hardware:** RTX PRO 4500 Blackwell (sm_120, cu128) — NOT H100  
**Data:** FineWeb sp1024 (8M train, 54M val tokens)  
**Model:** 9L d=512 seq=1024 | 29.4M params | 3000 steps  
**BPB method:** Sentencepiece byte counting (same formula as Parameter Golf),
but **this is PTQ-proxy BPB on one checkpoint, NOT official competition BPB.**
Official PG BPB requires training from scratch under 10-min/8×H100 rules.
These two BPB values are NOT comparable (invariant #12).  
**Date:** 2026-07-18

---

## Complete Results

| # | Format | Family | bpe | PTQ-proxy BPB | Δ vs FP32 | Status |
|---|--------|--------|-----|---------------|-----------|--------|
| 1 | **FP32** | IEEE FP | 32 | **2.7312** | — | master |
| 2 | FP16 E5M10 | IEEE FP | 16 | 2.7312 | +0.0000 | ✓ lossless |
| 3 | BF16 E8M7 | IEEE FP | 16 | 2.7312 | +0.0000 | ✓ lossless |
| 4 | GF14+ E5M8 | GF φ-rule | 14 | 2.7312 | +0.0000 | ✓ lossless |
| 5 | GF16+ E6M9 | GF φ-rule | 16 | 2.7312 | +0.0000 | ✓ lossless |
| 6 | GF20 E7M12 | GF φ-rule | 20 | 2.7312 | +0.0000 | ✓ lossless |
| 7 | **GF8+S E3M4** | **GF8 φ scaled** | **8** | **2.7313** | **+0.0001** | **✓ lossless ★** |
| 8 | INT8 | Integer | 8 | 2.7314 | +0.0002 | ✓ lossless |
| 9 | FP8 E4M3 | FP8 direct | 8 | 2.7316 | +0.0004 | ✓ lossless |
| 10 | FP8+S E4M3 | FP8 scaled | 8 | 2.7322 | +0.0010 | ✓ lossless |
| 11 | GF8 E3M4 | GF8 direct | 8 | 5.3735 | +2.6423 | ✗ BAD |
| 12 | **SQ-INT7** | **SmoothQuant** | **7** | **2.7314** | **+0.0002** | **✓ lossless ★** |
| 13 | INT7 | Integer | 7 | 2.7318 | +0.0006 | ✓ lossless |
| 14 | **SQ-INT6** | **SmoothQuant** | **6** | **2.7319** | **+0.0007** | **✓ lossless ★** |
| 15 | INT6 | Integer | 6 | 2.7343 | +0.0031 | ⚠ good |
| 16 | Ternary | BitNet | 1.58 | 4.5015 | +1.7703 | ✗ BAD (needs QAT) |

**8-bit ranking (by Δ):** GF8+S (+0.0001) → INT8 (+0.0002) → FP8 direct (+0.0004) → FP8+S (+0.0010)

---

## Key Findings

### GF8+S (φ-rule E3M4 scaled) — lowest Δ among 8-bit formats

```
GF8+S E3M4:  Δ = +0.0001
INT8:         Δ = +0.0002
FP8 E4M3:    Δ = +0.0004
FP8+S E4M3:  Δ = +0.0010
```

φ-rule gives M=4 instead of M=3 (FP8). Extra mantissa bit helps when
per-row scaling handles the range issue (max=31 vs 448).
Note: all four Δ values are at the noise floor — differences are small.
Do NOT claim "10× more accurate" (ratio of two tiny Δ at threshold).

### GF8 direct (no scaling) = BAD

Max value 31.0 clips weights >31 (common in embedding layers).
**Per-row scaling is essential for GF8.**

### SQ-INT6 = lossless at 3000 steps

```
INT6:    Δ = +0.0031 (good — measurable noise)
SQ-INT6: Δ = +0.0007 (lossless — 77% less error)
```

### Ternary needs BitNet QAT

PTQ ternary = BPB 4.50 (catastrophic).
BitNet b1.58 QAT = BPB 1.16 (competition result, Ifrim).
**Cannot compare — fundamentally different training method.**

---

## GF+ Adaptive Line (colleague's work, CPU synthetic + real weights)

GF+A = per-row selection from {φ-split, e2/e3, INT, NF4} pockets.

| Width | Best single | SQNR (dB) | GF+A SQNR | Note |
|-------|-------------|-----------|-----------|------|
| 8-bit | e2m5 | 43.52 | **43.89** | GF+A wins by 0.37 dB |
| 6-bit | φ-e2m3 | 31.42 | **31.72** | GF+A slightly higher (not tied) |
| 4-bit | NF4 | 19.42 | 19.42 | GF+A ties NF4 |

Header: 2 bits/row. MSE guarantee by construction (per-row argmin).

Honest limits: MSE advantage may not translate to BPB (QAT compensates).
LUT cost of 4-way decoder mux not measured. 4-bit NF4 slightly better
downstream (+0.0032 vs +0.0035 ΔBPB). GF+A not tested with GPU BPB.

---

## Competition Context (NOT comparable to our PTQ-proxy BPB)

| Format used | Official PG BPB | Author | Key |
|------------|-----------------|--------|-----|
| INT6 GPTQ | **1.0565** | codemath3000 | Winner |
| Ternary QAT | 1.1570 | Ifrim | BitNet b1.58 |
| INT6 QAT | 1.1502 | aruniyer | MLP3x |
| INT8 | 1.2244 | Baseline | Naive 8 GPU |
| **Our baseline** | **1.4715** | Trinity | 1 GPU, 1563 steps |
| **Our PTQ-proxy** | **2.7312** | Trinity | RTX PRO 4500, 3000 steps |

**Nobody in competition uses GF8, GF+, or SmoothQuant.** All novel contributions.
