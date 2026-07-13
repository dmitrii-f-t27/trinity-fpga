---
name: fpga-synth
description: AX7203 openXC7. 16 Tier-E 4/4 + 2 smoke (GF64/128). 11392/11392 bit-exact on silicon.
allowed-tools: Bash(docker *), Bash(ls *), Read, Grep, Glob, Write, Edit
---

# FPGA Pipeline — AX7203 XC7A200T

## Tier-E (2026-07-13): 16 cells 4/4 + 2 smoke
GF4-GF32 × {ADD,MUL}: 11392/11392 bit-exact, 0 failures.
GF64 ADD: smoke ✓. GF128 ADD: smoke ✓. GF256: CI building.

## Build recipe
yosys -nocarry -arch xc7 (NO abc9 for MUL) → nextpnr --fasm --placer heap → fasm → frames → bit

## Flash (no sudo)
python3 hardware/tools/trinity_flash.py <bitstream>
