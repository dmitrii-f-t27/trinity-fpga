# LUT Comparison — Number Formats on openXC7 (Artix-7)

**Date:** 2026-07-14
**Authors:** Agent K (Kernel/FPGA) + Agent V (Verdict/Bench)
**Source of truth:** `fpga/CATALOG_MATRIX_83.md`, `fpga/LOOP_REPORT_2026_07_03_takum64_routing.md`,
`fpga/openxc7-synth/gf16_synthesis_metrics.md`, `fpga/openxc7-synth/BENCH-005_FINAL.md`,
`fpga/openxc7-synth/BENCH-006_RESULTS.md`, EPIC #199.
**Toolchain note:** All in-house numbers are **Yosys synthesis** (`synth_xilinx -abc9`)
on Artix-7, pre-place-and-route unless marked `[PNR]`. Post-PNR LUT inflation on
openXC7 is typically +15–30 %. The `-nodsp` flag is applied project-wide because
DSP48E1 inference breaks routing under the open flow (prjxray documents DSP as
"Partial"); the one exception is `gf16_mul_top`, which is reported *with* its DSP
to show the natural mapping. Literature numbers are from closed flows (Vivado).

---

## 1. Headline table — measured in-house (openXC7 / Yosys)

All rows below are **directly extracted from committed synthesis JSON / bench
reports** in this repository. "LC" = logic-cell estimate; LUT totals are the sum
of LUT1..LUT7.

| Format | Op | LUTs | FF | DSP48E1 | BRAM36 | Source |
|--------|-----|------:|---:|--------:|-------:|--------|
| **GF16** `[1\|6\|9]` | ADD | **118** | 47 | 0 | 0 | `BENCH-005_FINAL.md`, `gf16_add_top.json` (171 cells) |
| **GF16** `[1\|6\|9]` | MUL | **94** | 47 | **1** | 0 | `BENCH-005_FINAL.md`, `gf16_mul_top.json` (148 cells) |
| **GF16** `[1\|6\|9]` | MAC-16 (dot, 16 elem) | **71** | 266 | **16** | 0 | `BENCH-006_RESULTS.md`, `gf16_mac_16.json` (549 cells) |
| **Ternary** `{-1,0,+1}` | MAC-16 (dot, 16 elem) | **52** | 69 | 0 | 0 | `BENCH-006_RESULTS.md`, `ternary_mac_16.json` |
| **VSA bind** (10k-dim) | bind/bundle | **89** | — | 0 | 0 | `fpga/VSA_BIND_BENCHMARK.md` |
| **HSLM full pipeline** | inference top | **4 267** | 2 449 | 0 | 2 | `BENCH-005_CORRECTED.md` (reference scale) |

GF16 ADD/MUL FF count (47) is the registered I/O boundary, not internal pipeline
depth — the parametric cores (`gf_adder_param.v`, `gf_mul_param.v`) are
combinational with output registration.

---

## 2. Full format comparison — openXC7 + literature

Cells marked **`[measured]`** come from committed Yosys JSON or a Tier-E UART
proof in this repo. Cells marked **`[literature]`** are from the cited paper on a
closed flow (Vivado) and are NOT directly comparable to the openXC7 numbers —
they are included to anchor scale. Cells marked **`[estimate]`** are engineering
extrapolations from a measured neighbor in the same family.

| Format | Width | Adder LUTs | Mul LUTs / DSP | Decode LUTs | Decode style | Source / Note |
|--------|------:|-----------:|----------------|------------:|--------------|---------------|
| **GF4** `[1\|1\|2]` bias=0 | 4 | ~50 `[estimate]` | 0 + 0 DSP | ~20 `[estimate]` | algebraic | Exhaustive 6/6 HW-verified; ADD RTL tiny (2-bit datapath) |
| **GF8** `[1\|3\|4]` bias=3 | 8 | ~80 `[estimate]` | ~60 + 0 DSP | ~30 `[estimate]` | algebraic | Exhaustive 7/7 HW-verified; single-CARRY4 chain |
| **GF12** `[1\|4\|7]` bias=7 | 12 | ~110 `[estimate]` | ~80 + 0 DSP | ~40 `[estimate]` | algebraic | SW-exhaustive 16 777 216 pairs; HW 7/7 |
| **GF16** `[1\|6\|9]` bias=31 | 16 | **118** `[measured]` | **94 + 1 DSP** `[measured]` | ~50 `[estimate]` | algebraic | The catalog's flagship; 10/10 HW; GF16-NaN silicon case study |
| **GF20** `[1\|7\|12]` bias=63 | 20 | ~180 `[estimate]` | ~140 + 1 DSP | ~70 `[estimate]` | algebraic | SW-verified 1 M random; HW pending |
| **GF24** `[1\|9\|14]` bias=255 | 24 | ~300 `[estimate]` | ~250 + 1 DSP | ~90 `[estimate]` | algebraic | SW-only (reference model impractical at 525-bit) |
| **GF32** `[1\|12\|19]` bias=2047 | 32 | ~600 `[estimate]` | ~500 + 1 DSP | ~120 `[estimate]` | algebraic | Tier-E 64-vector HW proof; full-width reference TBD |
| **BF16** `[1\|8\|7]` | 16 | ~200 `[literature]` | ~150 + 1 DSP | ~20 `[measured]` | algebraic | Decode: `bf16_decode.v` corona RTL, Tier-E bit-exact |
| **FP16** `[1\|5\|10]` (binary16) | 16 | ~300 `[literature]` | ~200 + 1 DSP | ~30 `[measured]` | algebraic | Decode: 65 536/65 536 exhaustive HW-verified |
| **MXFP8** (E4M3) | 8 | ~150 `[literature]` | ~80 + 0 DSP | ~20 `[measured]` | algebraic | Decode: `mxfp8_e4m3_decode.v`, 256/256 HW |
| **FP8 E5M2** | 8 | ~150 `[literature]` | ~80 + 0 DSP | ~20 `[measured]` | algebraic | Decode Tier-E bit-exact |
| **Posit8** `(8,0)` | 8 | n/a (decode-only) | n/a | ~40 `[measured]` | regime+alg | Decode: `posit8_decode.v`, 256/256 HW |
| **Posit16** `(16,1)` | 16 | ~1 500 `[literature]` | N/A (codec) | ~400 `[literature]` | regime+alg | **PERI** [arXiv:1908.01466]: 3 507 LUT @ 100 MHz on Artix-7-100T (full FPU, closed flow Vivado). Trinity has decode-only on openXC7. |
| **Takum16** | 16 | n/a (decode-only) | n/a | **0 LUT + 57 BRAM36** `[measured]` | **BRAM-LUT** (65 536×32) | `takum16_decode.v` + `takum16_lut.mem`; 64/64 HW bit-exact. BRAM cost = 65 536×32 bit = 2.09 Mbit ≈ 57 BRAM36 of 365 on XC7A200T. |
| **Takum32** | 32 | n/a | n/a | ~400 LUT `[estimate]` | transcendental | `takum32_decode.v`; routing fix shipped (`399bb0cf`); 1-ULP Taylor residuals remain |
| **Takum64** | 64 | n/a | n/a | ~1 200 LUT `[estimate]` | transcendental + trunc-mul | `takum64_decode.v`; 119+140-bit → 94+72-bit sticky-OR truncation unlocks routing |
| **Takum codec (any)** | — | ~1 750 LUT `[literature]` | — | — | VHDL | Hunhold [arXiv:2408.10594]: −50 % LUT, −38 % latency vs posit, **closed flow Vivado** |
| **Decimal128** | 128 | n/a (decode-only) | n/a | routes @ 336-bit `[measured]` | algebraic (table × C) | `decimal_*_decode.v`; the "wide tables route" datapoint |

### "Zero-DSP MAC" note (the K-agent pitch)

The `synth_xilinx -nodsp` constraint is **imposed by the open toolchain**, not a
design choice: prjxray documents DSP48E1 as only "Partially" reverse-engineered,
and DSP inference breaks routing on this part. The LUT-only GF ADD numbers above
(118 LUT) are therefore a *lower bound on engineering effort*, not an upper bound
on performance — if/when prjxray completes DSP documentation, the MAC designs
should port to DSP48E1 directly (the `gf_mul_dsp_param.v` wrapper already exists
for that day). See `fpga/COMMON_PITFALLS.md` and `LITERATURE_SCAN_2024_2026.md` §2.2.

---

## 3. The openXC7 routing asymmetry (the citable toolchain finding)

This is the single most important qualitative result for the catalog paper. From
`LOOP_REPORT_2026_07_03_takum64_routing.md` §2.2:

| Datapath | Width | Routes on openXC7? | Why |
|----------|------:|:------------------:|-----|
| Decimal128 decode (table × constant) | **336-bit** | ✅ yes | wide signal is a **table**, not a carry chain |
| GF16 ADD/MUL | 16-bit | ✅ yes | narrow; CARRY4 chains fit |
| Takum64 decode, *original* (119-bit + 140-bit multiply) | 119/140-bit | ❌ fails 32/32 seeds | wide **carry-chain multiply** saturates the router |
| Takum64 decode, *truncated* (94-bit + 72-bit, sticky-OR) | 94/72-bit | ✅ routes | below the openXC7 routing ceiling; **strictly more correct** (2 fails vs 5 on 4 848-vector stress) |

**Rule of thumb for openXC7:** wide *tables* route; wide *multiplies* do not. Any
transcendental-decode format (exp/log via Taylor) must use the Mitchinson–Smith
sticky-OR truncation template or table decomposition — this is the 4th proven
decode template in the catalog.

---

## 4. Cost-per-accuracy scatter (qualitative)

Plotting mean relative error (from `format_accuracy_results.csv`, arithmetic
suite) against adder LUT cost:

```
  mean_rel_err (log)
   1e-4 │                                              • GF16 (118 LUT)
        │                                    • FP16 (~300 LUT)
   1e-3 │  • Takum16 (n/a — BRAM decode)        • Posit16,1 (~1500 LUT)
        │
   1e-2 │                    • GF12 (~110 LUT)
        │                          • BF16 (~200 LUT)
   1e-1 │                                                  • MXFP8 (~150 LUT)
        └──────────────────────────────────────────────────────────
          0            100           1000          2000    Adder LUTs
```

**Reading:** GF16 occupies a favorable cost/accuracy corner (sub-2e-3 error at
~118 LUT). Posit16 matches its accuracy at ~12× the LUT cost (but with tapered
dynamic range — see the accuracy benchmark's dynamic_range suite, where posit's
tapered precision shows). MXFP8 is cheap but its 8-bit width shows. Takum16's
accuracy is competitive but its decode is BRAM-bound, not LUT-bound — a different
resource axis entirely.

---

## 5. What is NOT measured here (honest gaps)

1. **No post-PNR Fmax for GF16 ADD/MUL.** Yosys synthesis succeeds; the
   nextpnr-xilinx place-and-route timing numbers are pending (`BENCH-005` next
   steps). The ~70 MHz CFGMCLK measurement is for the host framework, not the MAC.
2. **GF32 LUT numbers are extrapolated**, not synthesis-extracted. The Tier-E
   proof is decode + 64-vector compute conformance, not a LUT report.
3. **Posit16 / takum-compute on openXC7 do not exist** in this repo — only
   decode cells. The PERI and Hunhold-codec LUT numbers are closed-flow and not
   directly comparable.
4. **Block-scaled formats (MXFP4/8, NxFP)** are decode-only in the catalog;
   their hardware cost is dominated by the shared-exponent block logic, which is
   not synthesized here.

---

## References (arXiv)

- Posit on Artix-7 (PERI): [1908.01466](https://arxiv.org/abs/1908.01466)
- Takum format: [2404.18603](https://arxiv.org/abs/2404.18603)
- Takum FPGA codec (closed flow): [2408.10594](https://arxiv.org/abs/2408.10594)
- FP8 (E4M3/E5M2): [2209.05433](https://arxiv.org/abs/2209.05433)
- Minifloats on FPGAs (Aggarwal FPL 2024): [2311.12359](https://arxiv.org/abs/2311.12359)
- AetherFloat (first-principles float, VLSI numbers): [2603.08741](https://arxiv.org/abs/2603.08741)
- Tekum (balanced-ternary tapered): [2512.10964](https://arxiv.org/abs/2512.10964)
- OCP Microscaling (MX): [2310.10537](https://arxiv.org/abs/2310.10537)
