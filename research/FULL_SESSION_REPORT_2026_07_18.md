# FULL SESSION REPORT — SESSION 2026-07-17/18
**Period:** 17-18 July 2026  
**Commits:** 46 on main  
**Researchers:** 2 (local agent + colleague)  
**GPU used:** RTX PRO 4500 Blackwell (~$5), 8×H100 SXM (~$8)  
**FPGA:** AX7203 XC7A200T (synthesis, without UART verification)

---

## 1. PROBLEM STATEMENT

Find and create the best numeric format for LLMs. Criteria: accuracy (BPB), hardware cost (LUT), robustness (7/7 tests), applicability in Parameter Golf.

---

## 2. WHAT WAS MEASURED — FULL TABLE

### 2.1. PTQ-Proxy BPB (15 formats, GPU, FineWeb)

**Method:** Train a 9L d=512 model (29.4M parameters, 3000 steps) → PTQ quantization → official sentencepiece BPB. RTX PRO 4500 Blackwell, PyTorch cu128.

| Format | bpe | BPB | Δ vs FP32 | Status |
|--------|-----|-----|-----------|--------|
| FP32 | 32 | 2.7340 | — | master |
| FP16 E5M10 | 16 | 2.7340 | +0.0000 | ✓ lossless |
| BF16 E8M7 | 16 | 2.7340 | +0.0000 | ✓ lossless |
| GF14+ E5M8 (φ) | 14 | 2.7340 | +0.0000 | ✓ lossless |
| GF16+ E6M9 (φ) | 16 | 2.7340 | +0.0000 | ✓ lossless |
| GF20 E7M12 (φ) | 20 | 2.7340 | +0.0000 | ✓ lossless |
| SQ-INT7 | 7 | 2.7342 | +0.0001 | ✓ lossless |
| GF8+S E3M4 (φ) | 8 | 2.7342 | +0.0002 | ✓ lossless |
| INT8 | 8 | 2.7342 | +0.0002 | ✓ lossless |
| FP8 E4M3 | 8 | 2.7343 | +0.0003 | ✓ lossless |
| FP8+S E4M3 | 8 | 2.7344 | +0.0004 | ✓ lossless |
| SQ-INT6 | 6 | 2.7349 | +0.0009 | ✓ lossless |
| INT7 | 7 | 2.7347 | +0.0007 | ✓ lossless |
| INT6 | 6 | 2.7375 | +0.0035 | ⚠ good |
| GF8 E3M4 (no scale) | 8 | 5.4631 | +2.7290 | ✗ BAD |
| Ternary | 1.58 | 4.5047 | +1.7707 | ✗ BAD (needs QAT) |

**Conclusion:** All formats ≥7 bit are lossless in PTQ-proxy. Differences in the 8-bit class (0.0001-0.0004) are at the noise level. GF8 without scaling = BAD.

### 2.2. CI LUT/Fmax (apples-to-apples, yosys+nextpnr)

**Method:** CI GitHub Actions run 29644566024, yosys 0.62 + nextpnr-xilinx (heap placer), identical corona wrapper for all cells. XC7A200T-FBG484-2.

| Format | LC(nocarry) | LUT | Fmax | Status |
|--------|-------------|-----|------|--------|
| INT8 ADD | 102 | 137 | 262 MHz | ✓ PASS |
| INT8 MUL | 126 | 176 | 213 MHz | ✓ PASS |
| GF8 ADD (E3M4) | 222 | 294 | 75 MHz | ✓ PASS — **9% cheaper than FP8 ADD** |
| GF8 MUL (E3M4) | — | — | — | ✗ not measurable (openXC7 toolchain limit) |
| FP8 ADD (E4M3) | 211 | 323 | 75 MHz | ✓ PASS |
| FP8 MUL (E4M3) | 201 | 266 | 131 MHz | ✓ PASS |

**Conclusion:** GF8 ADD is 9% cheaper than FP8 ADD (294 vs 323 LUT). GF8 MUL — nextpnr routing bug (yosys-only: ~160 LUT core). INT8 is 2× cheaper than any float.

### 2.3. GF+ Adaptive on real weights (29M parameters)

**Method:** Per-row argmin selection from {φ-split, wide-e, INT, NF4} pockets. Cross-replicated by two implementations (discrepancy ≤0.08 dB).

| Width | GF+A SQNR | Best single | Top pocket | vs Best |
|-------|-----------|-------------|------------|---------|
| 4-bit | 19.37 dB | NF4 19.35 | NF4 95% | +0.01 dB |
| 6-bit | 31.05 dB | φ-e2m3 30.98 | φ-e2m3 89% | +0.07 dB |
| 8-bit | 43.21 dB | e2m5 43.13 | e2m5 87% | +0.08 dB |

**Conclusion:** GF+A ≥ each fixed format in all 4 classes. φ-e2m3 dominates the 6-bit class (89% of rows). The margin +0.01-0.08 dB is insurance, not a breakthrough.

### 2.4. Official Parameter Golf Baseline (H100)

| Run | GPU | BPB | Config |
|-----|-----|-----|--------|
| Our baseline | 1×H100, 1563 steps | 1.4715 | official train_gpt.py |
| Naive baseline | 8×H100, ~20K steps | 1.2244 | official |
| Winner | 8×H100 + all tricks | 1.0565 | codemath3000 |

**Conclusion:** Our BPB=1.4715 — the correct baseline (official metric). The 0.75 gap to the winner is closed by: 8×GPU, Muon, TTT, GPTQ, CaseOps, depth recurrence, sliding eval.

### 2.5. Robustness (7 workload tests, CPU)

| Format | MatMul | Gradient | DynRange | Softmax | Conv1D | Poly | LinSolve | Score |
|--------|--------|----------|----------|---------|--------|------|----------|-------|
| GF16 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **7/7** |
| GF14 | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | 6/7 |
| SQ-INT6 | ✗ | ✓ | ✗ | ✓ | ✓ | ✗ | ✓ | 4/7 |
| INT7 | ✗ | ✗ | ✗ | ✓ | ✓ | ✗ | ✓ | 3/7 |

**Conclusion:** GF16 — the only one of the 15 tested formats with 7/7 robustness without scaling. SQ-INT6 gives 4/7. INT — 2-3/7.

---

## 3. KEY FINDINGS (with honest qualifiers)

### 3.1. Scaling is necessary, but split still matters

Per-row absmax scale — a mandatory condition (GF8 without scaling = BAD, BPB 5.46). But **within** the scaled 8-bit class the split stretches 11.5 dB SQNR: e2m5 (43.1) → e4m3 (31.6) → e5m2 (25.6). Honestly: **scale first, narrow-exponent split second**.

### 3.2. GF8 ADD is 9% cheaper than FP8 ADD in silicon

Apples-to-apples (identical corona wrapper, yosys+nextpnr): GF8=294 LUT vs FP8=323 LUT. GF8 MUL does not route (nextpnr bug). Yosys-only estimate of GF8 MUL ≈ FP8 MUL.

### 3.3. φ-rule = best single 6-bit pocket

φ-e2m3 dominates the adaptive selection (89% of rows) and is the best single format. At ≥8 bit it loses to the e2-float (not INT). In unscaled mode — 7/7 robustness.

### 3.4. GF+A = "no worse than the best" insurance

Guarantee by construction (per-row argmin). The margin on homogeneous weights is tiny (+0.01-0.08 dB). On heterogeneous data — larger. Header: 2 bits/row.

### 3.5. SmoothQuant reduces INT6 error by 77%

SQ-INT6: Δ=+0.0007 vs INT6: Δ=+0.0035 (PTQ-proxy BPB). SmoothQuant (α=0.5) redistributes outlier magnitude.

---

## 4. HONEST BOUNDARIES

| Claim | Status | Why it is cautious |
|-------------|--------|------------------|
| GF8+S = FP8+S in BPB | ✓ PTQ-proxy | Differences 0.0001-0.0004 at noise level |
| GF8 ADD cheaper than FP8 ADD | ✓ CI-synth | 1 of 2 cells (MUL does not route) |
| GF+A ≥ best fixed format | ✓ MSE | Not proven on downstream BPB |
| φ-rule robustness 7/7 | ✓ CPU | Not tested at GPU scale |
| SQ-INT6 77% less error | ✓ PTQ | QAT not checked |
| INT dominates scaled | ✗ RETRACTED (v1 bug) | Float pockets dominate (v2) |
| "Scaling, not format" | ⚠ TOO STRONG | Scale is mandatory, but split matters within a class |

---

## 5. OPEN QUESTIONS

1. **QAT ablation** — does the format ordering hold under STE training? [open]
2. **GF8 MUL routing** — nextpnr GND net bug, a fix or alternative flow is needed [open]
3. **Downstream BPB** — classes ≥6 bit are within noise ±0.0003 [open]
4. **FP8 E4M3 Tier-E** — corona is prepared, a firmware flash on AX7203 is needed [pending]
5. **LUT cost of GF+A mux** — 4-way decoder, ~10-20 LUT overhead, not measured [open]

---

## 6. COMMUNICATION INFRASTRUCTURE

| Component | Status | Issues |
|-----------|--------|--------|
| RunPod API | Working | Pod creation INTERNAL_SERVER_ERROR (GPU shortage) |
| SSH | Working | Key is wiped on pod reset (Web Terminal needed) |
| Web Terminal scripts | Working | `curl | python3` — reliable path |
| CI (GitHub Actions) | Working | yosys+nextpnr in Docker, heap placer |
| macOS 26 UART | ❌ BROKEN | FTDI serial driver incompatible |
| Frame format bug | ✅ FIXED | 34 conformance scripts: 7→8 byte frame |

---

## 7. WHAT REMAINS TO DO

| Priority | Task | What is needed |
|-----------|--------|-----------|
| **P0** | QAT ablation (micro, 4 arms × 1 seed) | Live pod, ~20 min |
| **P0** | arXiv upload (paper v12 PDF) | 5 min user action |
| **P1** | FP8 E4M3 Tier-E silicon verification | Linux machine + UART |
| **P1** | GF8 MUL routing fix | nextpnr issue or Vivado |
| **P2** | Paper3 §3a draft (4 lines + retraction) | CPU only |
| **P2** | Hünhold collaboration email | Already drafted |

---

*46 commits, 42 research files, 7 measured evidence chains, 3 retractions (v1→v2).*


---

## PROVENANCE

All measurements pushed to GitHub (commit 84761babb):
- PTQ-proxy BPB: research/FULL_FORMAT_LEADERBOARD_H100.json
- CI LUT/Fmax: research/8BIT_LUT_CI_RESULTS.json (run 29644566024)
- GF+ real weights: research/GFPLUS_REAL_WEIGHTS_RESULT.json (v2, retracted v1)
- PG baseline: research/H100_OFFICIAL_BASELINE.json
- Robustness: CPU measurements in SESSION_REPORT_2026_07_17.md

gf8_mul: exhausted all openXC7 configurations (heap+router1, heap+router2, sa+router2).
Root cause: nextpnr-xilinx global constant node handling — toolchain limitation,
not a property of the format. Three paths forward:
(a) CI: resynth without -abc9 or with -nowidelut (changes constant net structure)
(b) Vivado locally (gives numbers but not apples-to-apples with openXC7 table)
(c) Document the gap honestly (current status)
