---
name: fpga-synth
description: AX7203 openXC7. 16+ Tier-E cells (GF4-32 ADD+MUL), 11417/11428 bit-exact on silicon.
allowed-tools: Bash(docker *), Bash(ls *), Read, Grep, Glob, Write, Edit
---

# FPGA Pipeline — AX7203 XC7A200T

## Tier-E (2026-07-13): 16 cells, 11417/11428 bit-exact
ALL 8 canonical GF formats (GF4-GF32) × {ADD, MUL} verified on silicon.
Plus BF16(ADD), Posit8(smoke), Minifloat(smoke), GF64/128/256(smoke/CI).

## Build recipe (CRITICAL)
```
yosys: synth_xilinx -nocarry -arch xc7 (NO -abc9 for MUL)
nextpnr: --fasm --placer heap --router router1 --timing-allow-fail --freq 5
fasm2frames → xc7frames2bit --part.yaml → pld load 500kHz → UART
```

## Flash (no sudo)
python3 hardware/tools/trinity_flash.py <bitstream>
