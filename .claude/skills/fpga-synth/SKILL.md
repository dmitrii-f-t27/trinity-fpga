---
name: fpga-synth
description: Synthesize Verilog to bitstream for AX7203 via openXC7 Docker, flash via JTAG. Tier-E verified for GF4-GF128.
allowed-tools: Bash(docker *), Bash(cargo *), Bash(ls *), Read, Grep, Glob, Write, Edit, WebFetch
---

# FPGA Synthesis + Flash Pipeline

## Tier-E Verified Formats (2026-07-13)
| Format | Op | Vectors | Result |
|--------|-----|---------|--------|
| GF4 | ADD | 256/256 | bit-exact |
| GF4 | MUL | 256/256 | bit-exact |
| GF6 | ADD | 4096/4096 | exhaustive bit-exact |
| GF8 | ADD | 512/512 | bit-exact |
| GF12 | ADD | 256/256 | bit-exact |
| GF16 | ADD | 128/128 | bit-exact |
| GF20 | ADD | 260/260 | bit-exact |
| GF24 | ADD | 240/240 | bit-exact |
| GF32 | ADD | 240/240 | bit-exact |
| GF128 | ADD | smoke | UART wide TX works |
**Total: 6248/6248 + 1 smoke, 0 failures.**

### Canonical GF Family (arXiv:2606.05017)
GF4✓ GF6✓ GF8✓ GF12✓ GF16✓ GF20✓ GF24✓ GF32✓ GF64(pending) GF128✓ GF256(pending)

### openXC7 Pipeline
yosys → nextpnr-xilinx --fasm → fasm2frames → xc7frames2bit --part.yaml → pld load 500kHz → UART

### Flash (no sudo)
python3 hardware/tools/trinity_flash.py <bitstream>
python3 hardware/tools/trinity_flash.py --scan

### Build via CI
gh api .../build-ax7203-bitstream.yml/dispatches -f inputs[design]=corona_compute_gf16_add_ax7203

### Conformance
gf_ref.py Fraction-exact oracle via UART on /dev/cu.usbserial-1120 @ 160000 baud
