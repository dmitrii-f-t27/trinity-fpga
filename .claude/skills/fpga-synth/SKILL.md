---
name: fpga-synth
description: "AX7203 openXC7. 16 Tier-E 4/4. GF64: timing root cause found (barrel shifter+priority encoder). arXiv pkg ready. Tekum benchmark done."
allowed-tools: Bash(docker *), Bash(ls *), Read, Grep, Glob, Write, Edit
---

# FPGA Pipeline — AX7203 XC7A200T

## Current State (2026-07-14, Wave 4)

| Axis | Count | Detail |
|------|-------|--------|
| SW-bitexact | 75/83 | Ceiling reached |
| decode-HW Tier-E | ~47 | Ceiling 71 |
| compute-HW Tier-E | 16 cells | GF4-GF32 × {ADD,MUL}, 11392/11392 |
| GF64+ | ~50-70% silicon | 2 timing paths identified |
| Tekum | Oracle + adder + benchmark | GF16 wins accuracy+LUT |
| arXiv pkg | Ready | abstract.bib+checklist in research/arxiv_submission/ |

## GF64 Root Cause Analysis (Wave 3-4)

TWO independent timing-critical paths in `gf_adder_param`:

1. **Barrel shifter** (43-bit shift by 25-bit amount) → **clamped** to 6-bit shift (MANT_BITS+4). Fix: applied.
2. **Priority encoder** (8-branch if/else on 64-bit data) → still too deep for CFGMCLK. Fix: pipeline.

**Best silicon score**: 359/512 (70.1%) with original shift-reg TX + -abc9 (no clamp).
**Clamp effect**: -0+0 case fixed, but overall score lower due to priority encoder timing.
**Definitive fix**: 2-stage pipeline (Stage 1: decode+shift+sticky → reg → Stage 2: add+norm+round+pack).

## Build Recipe

```
docker run --rm regymm ... bash -c '
  yosys -p "read_verilog gf_adder_param.v ${DESIGN}.v; synth_xilinx -abc9 -nocarry -arch xc7; write_json ${DESIGN}.json"
  nextpnr-xilinx --chipdb /chipdb-xc7a200tfbg484-2.bin ...
  fasm2frames ... && xc7frames2bit ...
'
```

**Critical**: `-abc9` is REQUIRED (removal = 70%→19% regression). `-nocarry` always.

## Tekum Head-to-Head Results (Wave 4)

| Format | Mean Rel Err | Add LUT | Dynamic Range |
|--------|-------------|---------|---------------|
| **GF16** | **1.58e-03** | **118** | 18 decades |
| tekum16 | 1.61e-03 | ~480 | 153 decades |
| takum16 | 1.93e-03 | ~1350 | 83 decades |

GF16: competitive accuracy at 4-11x lower LUT cost. Tapered formats win on range.

## LESSONS LEARNED (Waves 1-4)

1. HAS_INF per-format (only GF16)
2. cur_byte must be reg
3. iverilog is fast gate (Python model + inline TB)
4. Provenance before every flash
5. Trinity moat = catalog × open-source-silicon proof
6. Tekum = nearest competitor (GF16 wins on LUT)
7. DePIN + openXC7 reproducible = strongest niche
8. TX NBA race: use buffer+mux not shift-register
9. -abc9 REQUIRED (removal = catastrophic regression)
10. GF64 timing: barrel shifter clamp helps partially, pipeline needed
11. ELiTeFormer + MxGLUT validate zero-DSP thesis
12. Priority encoder on 64-bit data is a timing bottleneck

## Key Files

| File | Purpose |
|------|---------|
| `fpga/openxc7-synth/gf_adder_param.v` | Parameterized GF adder (with clamp) |
| `fpga/openxc7-synth/tekum16_adder.v` | tekum16 adder (509 lines, iverilog clean) |
| `conformance/gf_ref.py` | Golden oracle |
| `conformance/tekum_ref.py` | Tekum oracle |
| `conformance/gf64_conformance_ax7203.py` | GF64 silicon harness |
| `research/arxiv_submission/` | Paper package (abstract, bib, checklist) |
| `research/CATALOG_PAPER_DRAFT.md` | ~3800-word paper |
| `research/head_to_head.py` | GF vs tekum vs takum benchmark |
| `hardware/tools/bitstream_provenance.py` | Provenance |
| `src/trinity_node/attestation.zig` | DePIN attestation (Zig 0.16) |
