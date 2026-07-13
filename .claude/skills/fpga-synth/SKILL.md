---
name: fpga-synth
description: AX7203 openXC7. 16 Tier-E cells (GF4-GF32 × {ADD,MUL}), 11392/11392 bit-exact on silicon.
allowed-tools: Bash(docker *), Bash(ls *), Read, Grep, Glob, Write, Edit
---

# FPGA Pipeline — AX7203 XC7A200T

## Tier-E (2026-07-13): 16 cells, 11392/11392 bit-exact, 0 failures
ALL 8 canonical GF formats × {ADD,MUL} verified on silicon.
GF4(256) GF6(4096 exhaustive) GF8(512) GF12(256) GF16(128) GF20(260) GF24(240) GF32(240)

## Build recipe (CRITICAL)
yosys: synth_xilinx -nocarry -arch xc7 (NO -abc9 for MUL!)
nextpnr: --fasm --placer heap --router router1 --timing-allow-fail --freq 5

## Flash (no sudo)
python3 hardware/tools/trinity_flash.py <bitstream>

## COUNTED FACT (auditor-verified 2026-07-13)
16 canonical GF compute Tier-E 4/4 @ Wave 89
Ceiling 71/83 decode Tier-E unchanged.
GF64/128/256 NOT yet on silicon (CI built, flash pending).
BF16 ADD NOT bit-exact (11 rounding tie-breaks, excluded).
