---
name: fpga-synth
description: "AX7203 openXC7. 16 Tier-E 4/4. GF64 root cause: timing closure (43-bit barrel shifter). Pipeline fix = next wave."
allowed-tools: Bash(docker *), Bash(ls *), Read, Grep, Glob, Write, Edit
---

# FPGA Pipeline — AX7203 XC7A200T

## Current State (2026-07-14, Wave 3)

| Axis | Count | Detail |
|------|-------|--------|
| SW-bitexact | 75/83 | Ceiling reached |
| decode-HW Tier-E | ~47 | Ceiling 71 |
| compute-HW Tier-E | 16 cells | GF4-GF32 × {ADD,MUL}, 11392/11392 bit-exact |
| GF64+ | 359/512 (70.1%) | **Root cause: timing closure failure** |

## GF64 Root Cause (found Wave 3)

**NOT a logic bug** — the adder core passes all iverilog (6/6) and Python (1544/1544) tests.
**IS a timing closure failure** — the 43-bit barrel shifter path in `gf_adder_param` is too deep for CFGMCLK (~50-70 MHz) on XC7A200T.

Evidence:
- Same-sign same-exponent additions work (short path, no shift)
- Cross-exponent and zero cases fail (long path through barrel shifter)
- GF32 (23-bit barrel shifter) meets timing → 11392/11342
- Removing `-abc9` makes it WORSE (70% → 19%) — ABC9 is needed for optimization
- TX NBA race found and fixed (shift-register → buffer+mux) but didn't fix the core issue

**Fix: pipeline the adder** (add register stage after barrel shifter, breaking combinational depth).

## Synthesis Flag Matrix (MEASURED)

| Flags | GF64 ADD Score | Notes |
|-------|---------------|-------|
| `-abc9 -nocarry` | 70.1% (best) | ABC9 is needed — removal causes regression |
| `-nocarry -nodsp` (no abc9) | 19.2% | ABC9 removal = catastrophic |
| `-abc9 -nocarry -nodsp` | not tested | |

**Rule: always use `-abc9 -nocarry -arch xc7` for GF adders.**

## Build Recipe

```
docker run --rm -v "$(pwd):/work" regymm/openxc7:latest bash -c '
  yosys -p "read_verilog gf_adder_param.v ${DESIGN}.v; synth_xilinx -abc9 -nocarry -arch xc7; write_json ${DESIGN}.json"
  nextpnr-xilinx --chipdb /chipdb-xc7a200tfbg484-2.bin --json ${DESIGN}.json --xdc ax7203_corona.xdc --fasm ${DESIGN}.fasm --router router1 --timing-allow-fail --freq 10.0
  /prjxray/env/bin/fasm2frames --db-root .../prjxray-db/artix7 --part xc7a200tfbg484-2 ${DESIGN}.fasm ${DESIGN}.frames
  xc7frames2bit --part_file .../part.yaml --frm_file ${DESIGN}.frames --output_file ${DESIGN}.bit
'
```

## LESSONS LEARNED (all auditor-verified, Wave 1-3)

1. **HAS_INF is per-format** — only GF16 has Inf/NaN
2. **cur_byte must be reg** in always@(*)
3. **iverilog is the fast gate** — Python bit-model + iverilog before silicon
4. **Provenance before every flash** — bitstream_provenance.py
5. **Trinity's moat** = format catalog × open-source-silicon proof
6. **Tekum (2512.10964)** = nearest competitor; read before claiming novelty
7. **DePIN + reproducible openXC7** = strongest novel niche
8. **TX NBA race** — shift-register TX has conflicting NBAs; use buffer+mux pattern
9. **-abc9 is REQUIRED** — removing it causes 70% → 19% regression
10. **Timing closure** — GF64+ barrel shifter is too deep for CFGMCLK; pipeline fix needed
11. **ELiTeFormer (2607.03652) + MxGLUT (2607.01607)** — independent validation of zero-DSP thesis

## Key Files

| File | Purpose |
|------|---------|
| `fpga/openxc7-synth/gf_adder_param.v` | Parameterized GF adder (E/M configurable) |
| `fpga/openxc7-synth/gf_mul_param.v` | Parameterized GF multiplier |
| `conformance/gf_ref.py` | Golden oracle (Fraction-exact) |
| `conformance/gf64_conformance_ax7203.py` | GF64 silicon conformance harness |
| `conformance/verify_adder_e24.py` | Python bit-model of adder core |
| `conformance/tekum_ref.py` | Tekum oracle (tapered precision) |
| `hardware/tools/bitstream_provenance.py` | Source→bit SHA256 binding |
| `src/trinity_node/attestation.zig` | DePIN attestation (Ed25519, Zig 0.16) |
| `research/CATALOG_PAPER_DRAFT.md` | ~3750-word paper draft |
| `research/LITERATURE_SCAN_2024_2026.md` | 6-axis paper scan, 40+ arXiv IDs |
