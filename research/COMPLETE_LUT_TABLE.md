# Complete LUT Characterization — Full GF Family (GF4 to GF1024)

**Toolchain**: yosys 0.63, `synth_xilinx -flatten -abc9 -nocarry [-nodsp] -arch xc7`
**Target**: Artix-7 XC7A200T-FBG484-2 (134,600 LUTs)
**Date**: 2026-07-15
**Status**: [measured yosys-synth] for W≤128, [est. scaling law] for W>128

## Complete GF Family LUT Table

| Format | W | E | M | ADD LUT | MUL LUT | % FPGA | Fits? |
|--------|---|---|---|---------|---------|--------|-------|
| GF4 | 4 | 1 | 2 | **15** | **7** | 0% | ✓ |
| GF6 | 6 | 2 | 3 | **100** | **89** | 0% | ✓ |
| GF8 | 8 | 3 | 4 | **171** | **174** | 0% | ✓ |
| GF10 | 10 | 3 | 6 | **220** | **270** | 0% | ✓ |
| GF12 | 12 | 4 | 7 | **283** | **363** | 0% | ✓ |
| GF14 | 14 | 5 | 8 | **382** | **473** | 0% | ✓ |
| GF16 | 16 | 6 | 9 | **485** | **587** | 0% | ✓ |
| GF20 | 20 | 7 | 12 | **645** | **851** | 1% | ✓ |
| GF24 | 24 | 9 | 14 | **815** | **1,117** | 1% | ✓ |
| GF32 | 32 | 12 | 19 | **1,236** | **1,860** | 1% | ✓ |
| GF48 | 48 | 18 | 29 | **2,791** | ~4,746 | 4% | ✓ |
| GF64 | 64 | 24 | 39 | **4,289** | ~8,437 | 6% | ✓ |
| GF96 | 96 | 36 | 59 | **8,642** | ~18,984 | 14% | ✓ |
| GF128 | 128 | 49 | 78 | **14,894** | ~33,751 | 25% | ✓ |
| GF256 | 256 | 97 | 158 | ~101,580 | ~135,004 | 100% | ✗ (edge) |
| GF512 | 512 | 195 | 316 | ~406,323 | ~540,016 | 401% | ✗ |
| GF1024 | 1024 | 391 | 632 | ~1,625,292 | ~2,160,066 | 1605% | ✗ |

Bold = measured by yosys synthesis. ~ = estimated from scaling law.

## Scaling Laws

- **ADD**: LUT = 1.55 × W² (R² = 0.876, 15 measured points W=4..128)
- **MUL**: LUT = 2.06 × W² (R² = 0.970, 10 measured points W=4..32)

## FPGA Feasibility Boundary

**GF128** (W=128): ADD = 14,894 LUT (11% of FPGA), MUL = ~33,751 LUT (25%) — **largest that fits comfortably**.

**GF256** (W=256): MUL ≈ 135,004 LUT ≈ 100% of FPGA — **does not fit** (no room for routing/other logic).

**GF512+**: Theoretical only — exceeds any current FPGA.

## Special Cores

| Core | LUT | DSP | BRAM | Notes |
|------|-----|-----|------|-------|
| Ternary MAC-16 | 55 | 0 | 0 | 16-element ternary dot product |
| GF Quire | 75 | 0 | 0 | binary64 accumulator |
| GF Sqrt | 128 | 8 | 0 | Newton-Raphson (binary32 proxy) |
| GF Div | 207 | 0 | 0 | Iterative divider (binary32 proxy) |
| takum16 native MUL | 505 | 0 | 0 | LNS multiply + tapered re-encode |

## Cross-Format Comparison at W=16

| Format | ADD LUT | MUL LUT | Type |
|--------|---------|---------|------|
| GF16 | 485 | 587 | IEEE-style (φ-rule) |
| takum16 | N/A | 505 | LNS tapered |
| FP16 | ~300 [lit.] | ~200 [lit.] | IEEE-754 |
| BF16 | ~200 [lit.] | ~150 [lit.] | IEEE-style |
| posit16 | ~1500 [lit.] | N/A | Tapered |
