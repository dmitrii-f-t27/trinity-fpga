---
name: fpga-synth
description: AX7203 openXC7. 15 Tier-E cells (4/4 proof on #199), 11152/11152 bit-exact on silicon.
allowed-tools: Bash(docker *), Bash(ls *), Read, Grep, Glob, Write, Edit
---

# FPGA Pipeline — AX7203 XC7A200T

## Tier-E (2026-07-13): 15 cells published on #199 with 4/4 proof
GF4(ADD+MUL) GF6(ADD+MUL) GF8(ADD+MUL) GF12(ADD+MUL) GF16(ADD+MUL) GF20(ADD+MUL) GF24(ADD+MUL) GF32(ADD)
Total: 11152/11152 bit-exact, 0 failures.

## Build recipe
yosys -nocarry -arch xc7 (NO abc9 for MUL) → nextpnr --fasm --placer heap → fasm2frames → xc7frames2bit --part.yaml

## Flash (no sudo)
python3 hardware/tools/trinity_flash.py <bitstream>
