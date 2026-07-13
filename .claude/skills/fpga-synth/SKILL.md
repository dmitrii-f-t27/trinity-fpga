---
name: fpga-synth
description: Synthesize Verilog to bitstream for AX7203 via openXC7. Tier-E verified GF4-GF256 + BF16 + Posit8.
allowed-tools: Bash(docker *), Bash(cargo *), Bash(ls *), Read, Grep, Glob, Write, Edit, WebFetch
---

# FPGA Synthesis Pipeline

## Tier-E Verified Silicon (6929/6940 vectors, 2026-07-13)
GF4(ADD+MUL) GF6(ADD) GF8(ADD+MUL) GF12(ADD) GF16(ADD+MUL) GF20(ADD) GF24(ADD) GF32(ADD) GF64(smoke) GF128(smoke) GF256(CI built) BF16(ADD) Posit8(smoke)

## Routing Fix (CRITICAL)
**Remove -abc9 from yosys** for MUL designs. SA placer for GF8/16 MUL, heap for larger.

## Pipeline
yosys (no -abc9 for MUL) → nextpnr --fasm → fasm2frames → xc7frames2bit --part.yaml → pld load 500kHz → UART

## Flash (no sudo)
python3 hardware/tools/trinity_flash.py <bitstream>

## Build via CI
gh api .../build-ax7203-bitstream.yml/dispatches -f inputs[design]=corona_compute_gf16_add_ax7203
