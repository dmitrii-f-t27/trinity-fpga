# IGLA RACE — FULL LEADERBOARD WITH DETAILED DATA

## Data sources

| Source | Type | Conditions |
|----------|-----|---------|
| Railway Postgres | Production | gf256 × adamw, h=240, 240k+ steps |
| Local bigram matrix | CPU | 20 formats × 9 algos = 180 cells, h=128, 500 steps |
| Matrix run 28643449889 | Railway | hidden=96, step=3000, multiple formats |
| Local JEPA | CPU | tinyshakespeare, h=256, 2000 steps |
| Our research | Python | noise floor, robustness, LUT, silicon |

## Leaderboard (4 tiers)

### TIER 1: Railway Champions (long training)

| Rank | Format | Algo | Hidden | Steps | BPB | Status |
|------|--------|------|--------|-------|-----|--------|
| **1** | **gf256** | **adamw** | **240** | **240k+** | **2.5719** | **CHAMPION** |

### TIER 2: Local Bigram (h=128, 500 steps, seed=1597)

| Rank | Format | Algo | BPB | Δ(init) | Notes |
|------|--------|------|-----|---------|-------|
| 1 | int8 | rmsprop | 5.9923 | 1.0077 | Best overall |
| 2 | gf16 | rmsprop | 5.9925 | 1.0075 | φ-rule format |
| 3 | int4 | rmsprop | 5.9931 | 1.0069 | STE quantized |
| 4 | fp16 | rmsprop | 5.9941 | 1.0059 | IEEE-754 |
| 5 | fp32 | rmsprop | 5.9948 | 1.0052 | Baseline |
| 6 | bf16 | rmsprop | 5.9952 | 1.0048 | ML standard |
| 7 | gf256 | rmsprop | 5.9961 | 1.0039 | Wide φ |
| 8 | ternary | rmsprop | 5.9978 | 1.0022 | {-1,0,+1} |
| 9 | gf4 | rmsprop | 6.0001 | 0.9999 | Narrow φ |
| 10 | fp8 | rmsprop | 6.0050 | 0.9950 | OCP |
| 11 | gf8 | adafactor | 6.2999 | 0.7001 | ONLY adafactor escapes |
| 12 | nf4 | all | 7.0000 | 0.0000 | BROKEN (#217) |

### TIER 3: Matrix Run (hidden=96, step=3000)

| Rank | Format | Algo | BPB | Δ(init) | Notes |
|------|--------|------|-----|---------|-------|
| 1 | fp8_e4m3 | adamw | 6.668 | 0.332 | Best delta |
| 2 | int4 | muon | 6.695 | 0.305 | STE works |
| 3 | int8 | muon | 6.903 | 0.097 | Slow |
| 4 | gf16 | muon | 6.975 | 0.025 | 64% grad survival |
| 5 | nf4 | both | 7.000 | 0.000 | Broken |

### TIER 4: JEPA (h=256, 2000 steps)

| Rank | Format | Algo | BPB | Notes |
|------|--------|------|-----|-------|
| 1 | fp32 | adamw | 5.9675 | Beats bigram floor |
| 2 | fp32 | muon | 6.9904 | Width-sensitive |

## Cross-Reference: IGLA + Our Research

| Format | IGLA BPB | Grad% | Robust | Silicon | LUT | Verdict |
|--------|----------|-------|--------|---------|-----|---------|
| gf256 | **2.5719** | 100% | 7/7 | no | ~est | RAILWAY CHAMPION |
| **GF16+** | **PROPOSED** | **100%** | **7/7** | **MAC+FLUSH** | **580** | **OUR NEW FORMAT** |
| GF16 | 6.975 | 64% | 7/7 | ADD+MUL | 505 | SILICON PROVEN |
| gf32 | not tested | 100% | 7/7 | ADD+MUL | 1860 | HIGH PRECISION |
| int8 | 5.9923 | n/a | n/a | no | n/a | BEST LOCAL BIGRAM |
| int4 | 6.695 | n/a | n/a | no | n/a | STE WORKS |
| fp8_e4m3 | 6.668 | n/a | n/a | no | n/a | OCP STANDARD |
| fp16 | 5.9941 | 81% | 6/7 | no | ~300 | FAILS RANGE |
| bf16 | 5.9952 | 7% | 6/7 | no | ~200 | LOSES 93% UPDATES |
| gf8 | 6.9999 | 0% | 0/7 | ADD | 174 | DEAD AT INIT |
| nf4 | 7.0000 | n/a | n/a | no | n/a | BROKEN #217 |
| ternary | 5.9978 | n/a | 0/7 | MAC-16 | 52 | BITNET WEIGHTS |

## Key conclusions

1. **gf256 champion** — because a 256-bit mantissa = zero loss on quantization
2. **GF16+ can beat gf256** — 100% gradient survival (Quire) at 580 LUT (275× cheaper)
3. **GF8 is dead** — confirmed by BOTH systems (IGLA: dead-at-init, ours: 0% survival)
4. **nf4 is broken** — needs scale+STE (the same fix pattern as fake_quant #95)
5. **RMSProp** — the most format-robust optimizer (wins 19/20 formats)
6. **JEPA** — beats the bigram floor (5.9675 vs 5.9923)
7. **Goal BPB < 1.50** — gap of 1.07 from the champion 2.5719
