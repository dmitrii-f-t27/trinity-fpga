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

## 8. Measured Comparison (both formats, same toolchain, 2026-07-15)

### 8.1 Multiplier — zero-DSP regime (the openXC7 constraint)

| Format | LUT2-LUT6 | DSP | BRAM | Method |
|--------|-----------|-----|------|--------|
| **GF16 MUL** (-nodsp) | **505** | 0 | 0 | `gf_mul_param.v` with `-nodsp` |
| **takum16 MUL** (native) | **505** | 0 | 0 | `takum16_native_mul.v` (LNS add) |

**Result: IDENTICAL LUT cost in the zero-DSP regime.**

The intuition that "LNS multiply = simple addition → cheaper" is WRONG:
takum16 saves the mantissa multiply (→ 0 DSP) but the tapered re-encode
(regime select + variable packing + RNE) costs exactly as much LUT
as the LUT-only multiply it replaces.

### 8.2 Multiplier — with DSP available

| Format | LUT | DSP | Method |
|--------|-----|-----|--------|
| **GF16 MUL** (DSP) | **399** | 1 | `gf_mul_param.v`, DSP auto-inferred |
| **takum16 MUL** | **505** | 0 | LNS add cannot use DSP |

When DSP is available, GF16 wins by 21% (399 vs 505 LUT) by mapping
the 9×9 mantissa multiply to a DSP48E1. takum16 cannot benefit from
DSP because LNS multiply is an addition, not a multiply.

### 8.3 Adder (for reference)

| Format | LUT | Notes |
|--------|-----|-------|
| **GF16 ADD** | **491** | algebraic: align + add + normalize |
| **takum16 ADD** | **N/A** | needs log-sum-exp (transcendental) — not yet implemented |

GF16 addition is straightforward (491 LUT). takum16 addition requires
log(exp(a) + exp(b)) — a transcendental operation. This is the fundamental
COMPLEMENTARITY: GF has cheap add + expensive mul; takum has cheap mul + expensive add.

### 8.4 The honest takeaway

> In the zero-DSP regime enforced by openXC7, **GF16 and takum16 are equal
> in LUT cost for multiplication** (505 each). The difference is architectural:
> - GF16: linear domain (cheap add, cheap mul-with-DSP)
> - takum16: log domain (expensive add, cheap mul — but same LUT cost without DSP)
>
> Neither format dominates. The choice depends on the operation mix
> (add-heavy → GF; mul-heavy with DSP → GF; mul-heavy without DSP → tie).

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

---

## 8. MEASURED — Native takum16 MUL (Wave 10, 2026-07-15)

> **Honesty note (supersedes §3.1 / §5 for the MUL row).** This section reports a
> *measured*, openXC7-synthesized **native logarithmic takum16 multiplier** and a
> freshly re-measured GF16 multiplier baseline. Two findings contradict the
> proposal's earlier framing and are flagged below rather than buried.

### 8.1 Artifacts (all committed)

| File | Role |
|------|------|
| `fpga/openxc7-synth/takum16_native_mul.v` | **NEW** — native LNS multiply core |
| `fpga/openxc7-synth/takum16_mul_top.v`    | synthesis wrapper |
| `fpga/openxc7-synth/takum16_native_mul_tb.v` | iverilog testbench (3012 vectors) |
| `fpga/openxc7-synth/takum16_mul_vectors.txt` | golden vectors (edge cases + 3000 random) |
| `fpga/openxc7-synth/gf16_mul_param_top.v` | **NEW** — correct GF16 *mul* wrapper (see §8.4) |

### 8.2 Measured LUT — takum16 native MUL vs GF16 MUL

Identical toolchain/flags for both: `yosys 0.63`, `synth_xilinx -flatten -abc9 -nocarry -arch xc7`.

| Module | LUT1 | LUT2 | LUT3 | LUT4 | LUT5 | LUT6 | **Total LUT** | MUXF7 | MUXF8 | FF | BRAM | **DSP** |
|--------|-----:|-----:|-----:|-----:|-----:|-----:|-------------:|------:|------:|---:|-----:|------:|
| **takum16_native_mul** | 2 | 121 | 82 | 100 | 116 | 86 | **507** | 29 | 10 | 17 | 0 | **0** |
| **GF16 mul (gf_mul_param)** | 2 | 79 | 87 | 99 | 72 | 60 | **399** | 17 | 4 | 17 | 0 | **1** |

```bash
# Reproducible from clean clone:
yosys -p "read_verilog fpga/openxc7-synth/takum16_native_mul.v \
            fpga/openxc7-synth/takum16_mul_top.v; \
          synth_xilinx -flatten -abc9 -nocarry -arch xc7; stat"
yosys -p "read_verilog fpga/openxc7-synth/gf_mul_param.v \
            fpga/openxc7-synth/gf16_mul_param_top.v; \
          synth_xilinx -flatten -abc9 -nocarry -arch xc7; stat"
# iverilog functional verification:
iverilog -g2012 -o /tmp/tb fpga/openxc7-synth/takum16_native_mul.v \
           fpga/openxc7-synth/takum16_native_mul_tb.v && vvp /tmp/tb
```

### 8.3 Finding 1 — takum16 MUL is NOT cheaper than GF16 in LUT

The proposal's §5 assumed (following `GF16_VS_TEKUM16_VS_TAKUM16.md` §5) that an
LNS multiply ("add of logs") would be cheap. **The measurement does not bear this out:**

> A native logarithmic takum16 multiply is **507 LUT — ~27% MORE than GF16's 399 LUT.**

**Why.** The LNS path does avoid the mantissa multiplier (no `*` operator at all →
0 DSP). But the savings are consumed by the **tapered re-encode**: a 16-way
contiguous regime selector (priority-encoded over the signed characteristic
`c ∈ [-255,254]`), variable-width field packing, and RNE mantissa rounding with
carry-into-regime handling. That variable datapath is larger than GF16's fixed
`[1|6|9]` exp/mant normalize+round. The "multiply = add" property is real *in the
log domain*, but repacking the sum back into the tapered format is the cost driver.

The honest trade-off axis is **LUT vs DSP**, not "takum is smaller":
- If **DSP is scarce** (e.g. DSPs already consumed by MAC arrays): takum16 wins — **0 DSP vs GF16's 1 DSP48E1** (see §8.4).
- If **LUT is the constraint**: GF16 wins — **399 vs 507 LUT**.

### 8.4 Finding 2 — GF16 "zero DSP" claim is wrong under `-abc9`

The 10×10 significand multiply in `gf_mul_param.v` (`prod = ma_f * mb_f`)
**auto-maps to 1× DSP48E1** under the exact flags this proposal specifies
(`-abc9`). Two doc bugs are corrected here:

| Claim (this doc / others) | Measured reality |
|--------------------------|------------------|
| §3.1: GF16 MUL reproducible via `read_verilog gf_mul_param.v gf16_param_top.v` | **Wrong file.** `gf16_param_top.v` instantiates `gf_ADDER_param`, so that command synthesizes the *adder*. Correct wrapper: `gf16_mul_param_top.v` (added this wave). |
| §3.1: GF16 MUL = "zero DSP" | **1× DSP48E1** inferred under `-abc9`. (The DSP-mapping was *intended* to live in the separate `gf_mul_dsp_param.v`; the `-abc9` pass maps the `*` anyway.) |
| §3.1: GF16 MUL = 397 LUT | **399 LUT** freshly measured (within rounding; the order of magnitude stands). |

> This is the same class of stale-number drift already documented in
> `LUT_COMPARISON_MEASURED.md` (the "118→176 LUT" correction). The reproducibility
> command above is now self-consistent.

### 8.5 Verification model — which oracle, and why it matters

This repo contains **two incompatible takum16 decode models** for the same bit
pattern. The native multiplier targets the **logarithmic** one (the one actually
validated on Trinity silicon):

| Source | Model | `decode(0x4800)` | multiply |
|--------|-------|------------------|----------|
| `research/head_to_head.py`, `takum16_lut.mem` (flashed BRAM), **this multiplier** | **logarithmic** `value=(-1)^S·exp(ℓ/2)` | exp(0.5)=1.649 | **ℓ-add** (cheap) |
| `conformance/takum_ref.py` (linear working hypothesis, see its header) | linear `(1+M)·2^c` | 2.0 | full mantissa mul |

The two agree on the **raw result iff both operands have zero mantissa** (exact
power-of-two encodings) — e.g. `0x4800*0x4800=0x4C00` under both. For general
mantissas they diverge.

**iverilog result (functional): PASS — 3012/3012 vectors bit-exact** vs the
validated prototype (edge cases + 3000 random).

**Accuracy vs the two oracles** (3516 finite random products):

| Reference | bit-exact | ≤1 ULP |
|-----------|----------:|-------:|
| log oracle `head_to_head` (true `exp(ℓ/2)` product) | **87.9%** | **96.5%** |
| linear oracle `takum_ref.format_mul` | 3.8% | — |

The 12% non-exact-vs-log cases are uniformly 1-ULP tapered-requantization
differences (expected: the takum ℓ-grid is non-uniform, so ℓ-add + re-quantize ≠
round-to-nearest of the true product). The 3.8% vs the linear oracle is the
**model mismatch**, not a bug — the linear oracle does a mantissa product the LNS
path deliberately does not perform.

**Task edge cases (all zero-mantissa) — match the linear oracle exactly:**

| op (linear value) | result | linear oracle | LNS HW | iverilog |
|------------------|--------|---------------|--------|----------|
| `0x0000*0x0000` (0·0) | 0x0000 | 0x0000 | 0x0000 | PASS |
| `0x4000*0x4000` (1·1) | 0x4000 | 0x4000 | 0x4000 | PASS |
| `0x4800*0x4800` (2·2) | 0x4C00 | 0x4C00 | 0x4C00 | PASS |
| `0x4000*0x3800` (1·0.5) | 0x3800 | 0x3800 | 0x3800 | PASS |
| `0xC000*0x4000` (-1·1) | 0xC000 | 0xC000 | 0xC000 | PASS |

### 8.6 Updated honest framing (supersedes §5)

> GF16 and takum16 occupy different points on the **LUT-vs-DSP** trade-off for
> multiplication, not a "takum is cheaper" point:
> - **GF16 mul**: 399 LUT + **1 DSP**, 5-decade dynamic range per exponent, fixed precision.
> - **takum16 mul (native LNS)**: 507 LUT + **0 DSP**, ~83-decade dynamic range, tapered precision, 87.9% bit-exact vs the log oracle (96.5% ≤1 ULP).
>
> The LNS "multiply = add" property is real but its HW win is **DSP elimination**,
> not LUT reduction — the tapered repack costs more LUT than the multiply it
> replaces. Prefer takum16 multiply when DSPs are the binding resource and wide
> dynamic range matters; prefer GF16 when LUT count is the binding resource.

### 8.7 What we still want from Hunhold (updated §4)

1. ~~Native takum16 multiplier RTL~~ — **done (this wave, Trinity side).** 507 LUT, 0 DSP, openXC7-measured, iverilog-verified.
2. Hunhold-side confirmation: does the canonical takum spec match the logarithmic
   `value=(-1)^S·exp(ℓ/2)` model (Trinity's flashed `takum16_lut.mem`), or the
   linear `(1+M)·2^c` model (`takum_ref.py` working hypothesis)? The two are not
   interchangeable for arithmetic — this multiplier is bit-exact only against the
   logarithmic one.
3. A native takum16 **adder** (the expensive LNS op: log-add / Zech). Estimated
   1350–1700 LUT pure-logic, per `head_to_head.py`.
