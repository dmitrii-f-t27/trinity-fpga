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

## LESSONS LEARNED (auditor-flagged)

1. **Check RTL before claiming architectural limits.** "fp32 M=23 boundary" was
   wrong — gf_adder_param uses native full-width (E=24, M=39 for GF64).
   Retracted on #199. ALWAYS verify against RTL source before publishing.

2. **Wide-format UART timing.** GF64+ (20-byte frames at 160kbaud) needs
   longer inter-frame delays. Use gf_wide_conformance.py with --delay 0.3.

3. **16 GF compute Tier-E 4/4 @ 2026-07-13 (Wave 89).** Ceiling 71/83
   decode Tier-E unchanged. GF64 ADD 166/240 = measurement artifact, NOT
   precision limit (fp32 hypothesis retracted).

4. **Routing fix: remove -abc9 from yosys for MUL.** Heap placer for wide.
