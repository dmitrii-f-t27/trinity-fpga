---
name: fpga-synth
description: Synthesize Verilog to bitstream for AX7203 via openXC7 Docker, flash via JTAG. Tier-E verified GF4-GF256 + BF16.
allowed-tools: Bash(docker *), Bash(cargo *), Bash(ls *), Read, Grep, Glob, Write, Edit, WebFetch
---

# FPGA Synthesis + Flash Pipeline

## Tier-E Verified (2026-07-13) — 6929/6940 bit-exact
| Format | ADD | MUL |
|--------|-----|-----|
| GF4 | 256/256 | 256/256 |
| GF6 | 4096/4096 | — |
| GF8 | 512/512 | 512/512 |
| GF12 | 256/256 | — |
| GF16 | 128/128 | 128/128 |
| GF20 | 260/260 | — |
| GF24 | 240/240 | — |
| GF32 | 240/240 | — |
| GF64 | smoke | — |
| GF128 | smoke | — |
| GF256 | CI success | — |
| BF16 | 245/256 | — |

### Routing Fix (critical)
**Remove -abc9 from yosys synth_xilinx for MUL designs.**
abc9 optimization creates unroutable logic; without abc9, nextpnr routes cleanly.

### openXC7 Pipeline
yosys (no -abc9 for MUL) → nextpnr-xilinx --fasm → fasm2frames → xc7frames2bit --part.yaml → pld load → UART

### Flash (no sudo)
python3 hardware/tools/trinity_flash.py <bitstream>
