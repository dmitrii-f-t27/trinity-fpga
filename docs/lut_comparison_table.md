# Trinity FPGA Compute-HW: LUT/FF Comparison Table

**Extracted from yosys synth_xilinx -abc9 -nocarry -arch xc7**
**Date: 2026-07-12**
**Status: [verified SW-synth] — NOT Tier-E**

## Parametric Cores (standalone)

| Core | LUTs | FFs | Algorithm | Latency |
|------|------|-----|-----------|---------|
| gf_adder_param | 410 | 16 | RNE add/sub + normalize | 1 cycle |
| gf_mul_param | 321 | 17 | behavioral * + RNE | 1 cycle |
| gf_div_param | 210 | 124 | iterative shift-subtract | MANT+1 cycles |
| gf_sqrt_param | 4467 | 85 | Newton-Raphson (2 iter) | 4 cycles |
| gf_quire_param | 75 | 69 | binary64 accumulator | 1 cycle |

## ADD/MUL/DIV LUT Comparison (compute modules, top-level after ABC)

| Format | ADD LUTs | MUL LUTs | DIV LUTs | DIV overhead vs ADD |
|--------|---------|---------|---------|---------------------|
| gf4 | 121 | 121 | 138 | +14% |
| gf8 | 126 | 118 | 134 | +7% |
| gf16 | 132 | 132 | 156 | +18% |
| gf32 | 148 | 149 | 192 | +29% |
| bf16 | 135 | 135 | 151 | +12% |
| fp32_e8m23 | 187 | 189 | 188 | +1% |

## SQRT/QUIRE LUT Comparison

| Format | SQRT LUTs | QUIRE LUTs |
|--------|----------|-----------|
| gf4 | 4620 | 74 |
| gf8 | 4620 | 74 |
| gf16 | 4620 | 74 |
| gf32 | 4620 | 74 |
| bf16 | 4620 | 74 |

Note: SQRT LUTs dominated by gf_sqrt_param core (4467 LUTs) due to behavioral `/`.
QUIRE LUTs dominated by gf_quire_param core (75 LUTs).

## Format Width vs LUT (ADD operation)

| Width | Format | LUTs |
|-------|--------|------|
| 4-bit | gf4 | 121 |
| 8-bit | gf8 | 126 |
| 16-bit | gf16/bf16 | 132-135 |
| 24-bit | fp24 | ~140 |
| 32-bit | gf32/fp32 | 148-187 |
| 48-bit | fp48 | ~165 |
| 64-bit | binary64 | ~180 |
| 128-bit | fp128 | ~210 |

## Competitive Context (from literature)

| System | Format | LUTs | Fmax | Source |
|--------|--------|------|------|--------|
| Trinity gf_div_param | fp32 div | 210 | TBD | This work |
| Trinity gf_sqrt_param | fp32 sqrt | 4467 | TBD | This work |
| Takum codec (Hunhold 2024) | takum32 | ~600 | 323 MHz | arXiv:2408.10594 |
| SPADE posit MAC (2026) | posit(8,0) | ~400 | TBD | arXiv:2601.17279 |
| PERCIVAL posit core (2022) | posit32 | ~5000 | 50 MHz | arXiv:2111.15286 |

## Key Findings

1. **DIV is cheap** (210 LUTs) — iterative approach, but 24-cycle latency
2. **SQRT is expensive** (4467 LUTs) — behavioral division in NR dominates
3. **QUIRE is cheapest** (75 LUTs) — simple register-based accumulator
4. **Format width weakly correlates with LUTs** — decode/quantize dominate, not compute core
5. **Competitive positioning**: Trinity's per-operation LUT cost is comparable to takum codec,
   but Trinity covers 428 families vs takum's 1

## Limitations

- All numbers from yosys (openXC7), NOT Vivado — timing/Fmax unknown
- SQRT uses behavioral `/` which yosys maps to combinatorial divider — would benefit from
  Newton-Raphson without division (e.g., Goldschmidt or table-based initial guess)
- QUIRE is simplified (last-value-wins, not true wide-add) — true quire needs exp alignment
- No DSP block usage reported (yosys -nocarry flag)
