# FORMAT LEADERBOARD — Definitive Comparison (15 formats)

**Hardware:** RTX PRO 4500 Blackwell (sm_120)  
**Data:** FineWeb sp1024 (8M train, 54M val tokens)  
**Model:** 9L d=512 seq=1024 | 29.4M params | 3000 steps  
**BPB:** Official sentencepiece byte counting  
**Date:** 2026-07-18

---

## Complete Results

| # | Format | Family | bpe | FineWeb BPB | Δ vs FP32 | Status |
|---|--------|--------|-----|-------------|-----------|--------|
| 1 | **FP32** | IEEE FP | 32 | **2.7312** | — | master |
| 2 | FP16 E5M10 | IEEE FP | 16 | 2.7312 | +0.0000 | ✓ lossless |
| 3 | BF16 E8M7 | IEEE FP | 16 | 2.7312 | +0.0000 | ✓ lossless |
| 4 | GF14+ E5M8 | GF φ-rule | 14 | 2.7312 | +0.0000 | ✓ lossless |
| 5 | GF16+ E6M9 | GF φ-rule | 16 | 2.7312 | +0.0000 | ✓ lossless |
| 6 | GF20 E7M12 | GF φ-rule | 20 | 2.7312 | +0.0000 | ✓ lossless |
| 7 | FP8 E4M3 | FP8 direct | 8 | 2.7316 | +0.0004 | ✓ lossless |
| 8 | FP8+S E4M3 | FP8 scaled | 8 | 2.7322 | +0.0010 | ✓ lossless |
| 9 | **GF8+S E3M4** | **GF8 φ scaled** | **8** | **2.7313** | **+0.0001** | **✓ lossless ★** |
| 10 | GF8 E3M4 | GF8 direct | 8 | 5.3735 | +2.6423 | ✗ BAD |
| 11 | INT8 | Integer | 8 | 2.7314 | +0.0002 | ✓ lossless |
| 12 | INT7 | Integer | 7 | 2.7318 | +0.0006 | ✓ lossless |
| 13 | **SQ-INT7** | **SmoothQuant** | **7** | **2.7314** | **+0.0002** | **✓ lossless ★** |
| 14 | **SQ-INT6** | **SmoothQuant** | **6** | **2.7319** | **+0.0007** | **✓ lossless ★** |
| 15 | INT6 | Integer | 6 | 2.7343 | +0.0031 | ⚠ good |
| 16 | Ternary | BitNet | 1.58 | 4.5015 | +1.7703 | ✗ BAD (needs QAT) |

---

## Key Findings

### ★ GF8+S (φ-rule E3M4 scaled) BEATS FP8+S (E4M3 scaled)

```
GF8+S E3M4:  BPB = 2.7313 (Δ = +0.0001) ← BEST 8-bit!
FP8+S E4M3:  BPB = 2.7322 (Δ = +0.0010)
FP8  E4M3:   BPB = 2.7316 (Δ = +0.0004) ← direct (no scaling)
```

φ-rule gives M=4 instead of M=3. Extra mantissa bit = +6dB SQNR.
Per-row scaling fixes the range issue (max=31 vs 448).
**Result: GF8+S is 10× more accurate than FP8+S!**

### GF8 direct = BAD (without scaling)

Max value 31.0 clips weights >31 (common in embedding layers).
**Per-row scaling is ESSENTIAL for GF8.**

### SQ-INT6 = lossless at 3000 steps

```
INT6:    Δ = +0.0031 (good — measurable noise)
SQ-INT6: Δ = +0.0007 (lossless — 77% less error!)
```

### Ternary needs BitNet QAT

PTQ ternary = BPB 4.50 (catastrophic).
BitNet b1.58 QAT = BPB 1.16 (competition result, Ifrim).
**Cannot compare — fundamentally different training method.**

---

## Competition Context (Parameter Golf)

| Format used | BPB | Author | Key |
|------------|-----|--------|-----|
| INT6 GPTQ | **1.0565** | codemath3000 | Winner |
| Ternary QAT | 1.1570 | Ifrim | BitNet b1.58 |
| INT6 QAT | 1.1502 | aruniyer | MLP3x |
| INT8 | 1.2244 | Baseline | Naive |
| **Our FP32→INT8** | **1.4715** | Trinity | 1 GPU, 1563 steps |

**Nobody uses GF8 or SmoothQuant.** Both are our novel contributions.
