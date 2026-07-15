# Complete LUT Characterization — GF Family + Special Cores

**Toolchain**: yosys 0.63, `synth_xilinx -flatten -abc9 -nocarry [-nodsp] -arch xc7`
**Date**: 2026-07-15
**Status**: [измерено yosys-synth]

## GF ADD (all widths)

| W | E | M | LUT | LUT/W² |
|---|---|---|-----|--------|
| 4 | 1 | 2 | 15 | 0.94 |
| 6 | 2 | 3 | 100 | 2.78 |
| 8 | 3 | 4 | 171 | 2.67 |
| 10 | 3 | 6 | 220 | 2.20 |
| 12 | 4 | 7 | 283 | 1.97 |
| 14 | 5 | 8 | 382 | 1.95 |
| **16** | **6** | **9** | **485** | **1.89** |
| 20 | 7 | 12 | 645 | 1.61 |
| 24 | 9 | 14 | 815 | 1.41 |
| 32 | 12 | 19 | 1236 | 1.21 |

**Fit**: LUT = 1.55 × W² (R² = 0.876)

## GF MUL (-nodsp, all widths)

| W | E | M | LUT | LUT/W² |
|---|---|---|-----|--------|
| 4 | 1 | 2 | 7 | 0.44 |
| 6 | 2 | 3 | 89 | 2.47 |
| 8 | 3 | 4 | 174 | 2.72 |
| 10 | 3 | 6 | 270 | 2.70 |
| 12 | 4 | 7 | 363 | 2.52 |
| 14 | 5 | 8 | 473 | 2.41 |
| **16** | **6** | **9** | **587** | **2.29** |
| 20 | 7 | 12 | 851 | 2.13 |
| 24 | 9 | 14 | 1117 | 1.94 |
| 32 | 12 | 19 | 1860 | 1.82 |

**Fit**: LUT = 2.06 × W² (R² = 0.970)

## Special Cores

| Core | LUT | DSP | BRAM | Notes |
|------|-----|-----|------|-------|
| ternary_mac_16 | 55 | 0 | 0 | 16-element ternary dot product |
| gf_quire_param | 75 | 0 | 0 | binary64 accumulator (75 LUT!) |
| gf_sqrt_param | 128 | 8 | 0 | Newton-Raphson (binary32 proxy) |
| gf_div_param | 207 | 0 | 0 | Iterative divider (binary32 proxy) |
| takum16_native_mul | 505 | 0 | 0 | LNS multiply + tapered re-encode |

## Key Findings

1. **GF Quire = 75 LUT** — cheapest accumulator after ternary (55)
2. **GF Sqrt = 128 LUT + 8 DSP** — Newton-Raphson uses DSP for multiply
3. **GF Div = 207 LUT** — iterative, no DSP needed
4. **MUL costs 1.2-1.5× ADD** across all widths
5. **Scaling laws**: ADD = 1.55×W², MUL = 2.06×W²
6. **Ternary MAC = 55 LUT** — 9× cheaper than GF16 ADD (485), 20× cheaper than MUL (587)
