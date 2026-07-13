---
name: fpga-synth
description: AX7203 openXC7 synthesis+flash. 18 Tier-E cells, 11177/11188 bit-exact on silicon.
allowed-tools: Bash(docker *), Bash(ls *), Read, Grep, Glob, Write, Edit, WebFetch
---

# FPGA Pipeline — AX7203 XC7A200T

## Tier-E: 18 cells, 11177/11188 bit-exact (2026-07-13)
GF4(ADD+MUL) GF6(ADD+MUL exhaustive) GF8(ADD+MUL) GF12(ADD+MUL) GF16(ADD+MUL) GF20(ADD+MUL) GF24(ADD) GF32(ADD) BF16(ADD) Posit8(smoke)

## Build recipe
yosys -nocarry -arch xc7 (NO abc9 for MUL) → nextpnr --fasm --placer heap → fasm2frames → xc7frames2bit --part.yaml

## Flash (no sudo)
python3 hardware/tools/trinity_flash.py <bitstream>

## Conformance
gf_ref.py Fraction-exact via UART @ 160000 baud
