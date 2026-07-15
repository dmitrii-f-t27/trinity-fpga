# Joint Benchmark Proposal: GoldenFloat GF16 vs Takum16 on openXC7

**Status**: [proposal for collaboration with Hunhold, arXiv:2404.18603]
**Date**: 2026-07-15
**Authors**: Vasilev (GoldenFloat) — seeking Hunhold (takum) collaboration

---

## 1. Motivation

Both GoldenFloat (GF) and takum are 2024-2026 number format families claiming
hardware friendliness. Neither has been benchmarked against the other on the
SAME open-source FPGA toolchain. This document proposes a joint methodology
and presents preliminary numbers from the GF side.

## 2. Methodology

### 2.1 Toolchain (identical for both formats)
```
yosys 0.63: synth_xilinx -flatten -abc9 -nocarry -arch xc7
nextpnr-xilinx: --chipdb xc7a200tfbg484-2.bin
Target: Artix-7 XC7A200T-FBG484-2 (ALINX AX7203)
```

### 2.2 Metrics
- **LUT count**: sum of LUT2..LUT6 from yosys stat (pre-PNR)
- **BRAM count**: BRAM36 blocks inferred
- **Fmax**: from nextpnr timing report (if achievable)
- **Accuracy**: mean relative error vs exact Fraction oracle, 4 suites
- **Dynamic range**: decades between min and max normal

### 2.3 Reproducibility
All commands runnable from clean clone:
```bash
make lut     # GF16 LUT measurement
make bench   # accuracy benchmark (7 formats)
make oracle  # 15 oracle self-tests
```

## 3. Preliminary Results (GF side, measured 2026-07-14)

### 3.1 GF16 Adder + Multiplier (measured on openXC7, yosys 0.63)

| Operation | LUT2-LUT6 | MUXF7/8 | FF | BRAM | DSP | Method |
|-----------|-----------|---------|-----|------|-----|--------|
| **ADD** | **491** | 16+5 | 17 | 0 | 0 | `gf_adder_param.v` |
| **MUL** | **397** | 17+4 | 17 | 0 | 0 | `gf_mul_param.v` |

Both fully parameterized, LUT-only (zero DSP, zero BRAM).
Reproducible: `yosys -p "read_verilog gf_adder_param.v gf16_param_top.v; synth_xilinx -flatten -abc9 -nocarry -arch xc7; stat"`

### 3.2 Silicon Verification (AX7203, IDCODE 0x13636093)

10 GF formats (GF4-GF32) × {ADD,MUL} = 20 cells, all bit-exact on silicon, 0 failures.
GF64 ADD: 70.1% (359/512) — timing closure ceiling on CFGMCLK (iverilog 9/9, RTL correct).

### 3.2 Accuracy Comparison (exact Fraction oracle, 1000 random ADDs)

| Format | Mean Rel Err | Max Rel Err | Dynamic Range |
|--------|-------------|-------------|---------------|
| **GF16** [1\|6\|9] | **1.58e-03** | 9.27e-02 | 18 decades |
| **takum16** | **1.93e-03** | 1.37e-01 | 83 decades |
| posit(16,1) | 1.36e-03 | 1.57e-01 | ~30 decades |
| FP16 [1\|5\|10] | 1.30e-03 | 4.58e-01 | 5 decades |
| MXFP8 (E4M3) | 7.10e-02 | 4.81e+00 | <1 decade |

### 3.3 GF16 Decode (algebraic, measured)
| Metric | Value |
|--------|-------|
| LUT | ~50 (estimated from parametric decode) |
| BRAM | 0 |

### 3.4 takum16 Decode (BRAM LUT approach)
| Metric | Value |
|--------|-------|
| LUT | ~0 (logic only — clocked BRAM read) |
| BRAM | **1× BRAM36** (65536-entry × 32-bit LUT) |
| Note | Requires pre-computed `takum16_lut.mem` |

## 4. What We Need from Hunhold (takum side)

1. **Native takum16 adder RTL** (not decode-to-FP32-and-add-back)
   - Currently: `takum16_decode.v` = BRAM LUT only, no native arithmetic
   - Needed: LNS-domain add (logadd), or algebraic if available
2. **Same toolchain synthesis**: run `yosys synth_xilinx -flatten -abc9 -nocarry -arch xc7` on takum16 adder
3. **Accuracy vectors**: 1000 random ADD pairs, exact oracle, for cross-validation
4. **Fmax**: if takum16 adder fits on Artix-7

## 5. Honest Framing (per goldenfloat-positioning.md)

> GF16 and takum16 occupy **different points on the area-vs-dynamic-range trade-off**:
> - GF16: 491 LUT, 0 BRAM, 18 decades dynamic range, algebraic add
> - takum16: ~0 LUT logic + 1 BRAM36, 83 decades dynamic range, LUT-based decode
>
> Neither format dominates. The choice depends on:
> - If BRAM is available and dynamic range is critical: takum16
> - If LUT-only (zero BRAM) and narrow range suffices: GF16
> - If the application needs on-the-fly decode without pre-computed LUT: GF16

## 6. Proposed Joint Paper Outline

**Title**: "GoldenFloat vs Takum on Open-Source Silicon: A Reproducible Benchmark"

**Sections**:
1. Introduction (format landscape, why open-source silicon matters)
2. Methodology (openXC7 toolchain, identical flags, AX7203 target)
3. GF16 results (LUT=491, accuracy=1.58e-3, 10 formats silicon-proven)
4. Takum16 results (Hunhold's measurements)
5. Comparison (area, accuracy, dynamic range, route-yield)
6. Discussion (when each format wins)
7. Conclusion (complementary, not competitive)

**Target venue**: CoNGA 2027 or ARITH 2027

## 7. Contact

Dmitrii Vasilev, ORCID 0009-0008-4294-6159
Repository: github.com/gHashTag/trinity-fpga
Reproducible: `make oracle && make repro && make bench && make lut`
