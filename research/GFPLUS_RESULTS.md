# GF+ Line — Complete Results Summary

## What was tested

GF+ extends GoldenFloat with **adaptive per-row format selection** (GF+A).
Each row picks the best format from a pocket: {φ-split, wide-e, INT, NF4}.

## Test Results [measured — CPU]

### Test A: Synthetic distribution sweep

No single split wins everywhere:
- 4-bit: NF4 best on Gaussian, INT4 best on uniform
- 6-bit: φ-e2m3 best overall
- 8-bit: e2m5 best overall (more mantissa than φ e3m4)

### Test B: Real model weights

| Width | GF+A SQNR | Best single | Single SQNR | Δ |
|-------|-----------|-------------|-------------|---|
| 8-bit | **43.89** | e2m5 | 43.52 | +0.37 dB |
| 6-bit | **31.72** | φ-e2m3 | 31.42 | +0.30 dB |
| 4-bit | 19.42 | NF4 | 19.42 | tied |

GF+A = best or equal in ALL cells. By construction (per-row argmin MSE).

### Our GPU confirmation [measured — RTX PRO 4500 Blackwell]

| Format | PTQ-proxy BPB | Δ | Note |
|--------|--------------|---|------|
| **GF8+S E3M4** | **2.7313** | **+0.0001** | lowest Δ among 8-bit |
| INT8 | 2.7314 | +0.0002 | |
| FP8 E4M3 | 2.7316 | +0.0004 | |
| FP8+S E4M3 | 2.7322 | +0.0010 | highest Δ among lossless 8-bit |

Note: all Δ values are at noise floor. Do not overstate differences.

## Honest Limitations

1. MSE advantage ≠ guaranteed BPB improvement (QAT compensates).
2. LUT cost of 4-way mux not measured (~10-20 LUT overhead).
3. 4-bit NF4 slightly better downstream on pure Gaussian.
4. GF8 direct (no scaling) = BAD (BPB 5.37).
5. GF+A not tested with GPU BPB on real model checkpoint.
6. QAT ablation not run — does e3m4 advantage hold under STE training?

## Pending Verification

1. **QAT ablation** (main gate): does e3m4 pocket advantage persist under
   STE training? Run: `run_gf8_on_runpod.py` on 8×H100.
2. **GF+ on real checkpoint**: `gfplus_pod_benchmark.py /workspace/model.pt`
