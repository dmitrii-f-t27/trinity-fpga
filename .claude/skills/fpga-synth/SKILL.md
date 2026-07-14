---
name: fpga-synth
description: "AX7203 openXC7. 16 Tier-E cells 4/4 proven. GF64 HAS_INF bug found+fixed. Bitstream provenance tooling added."
allowed-tools: Bash(docker *), Bash(ls *), Read, Grep, Glob, Write, Edit
---

# FPGA Pipeline — AX7203 XC7A200T

## Current State (2026-07-14)

| Axis | Count | Detail |
|------|-------|--------|
| SW-bitexact | 75/83 | Ceiling reached (8 structural terminal) |
| decode-HW Tier-E | ~47 unique | Ceiling 71 — biggest remaining gap |
| compute-HW Tier-E | 16 cells | GF4-GF32 × {ADD,MUL}, 11392/11392 bit-exact |
| GF64+ | Bug found | HAS_INF mismatch fixed, awaiting re-flash |

## Build Recipe (openXC7 Docker)

```
docker run --rm -v "$(pwd):/work" regymm/openxc7:latest bash -c '
  yosys -p "read_verilog gf_adder_param.v ${DESIGN}.v; synth_xilinx -abc9 -nocarry -arch xc7; write_json ${DESIGN}.json"
  nextpnr-xilinx --chipdb /chipdb-xc7a200tfbg484-2.bin --json ${DESIGN}.json --xdc ax7203_corona.xdc --fasm ${DESIGN}.fasm --router router1 --timing-allow-fail --freq 10.0
  /prjxray/env/bin/fasm2frames --db-root .../prjxray-db/artix7 --part xc7a200tfbg484-2 ${DESIGN}.fasm ${DESIGN}.frames
  xc7frames2bit --part_file .../part.yaml --frm_file ${DESIGN}.frames --output_file ${DESIGN}.bit
'
```

**Routing rules:**
- NO `-abc9` for MUL designs (breaks nextpnr routing)
- Use `--placer heap` for wide formats (GF20+)
- `-nocarry` always (carry chains break on this part)
- `-nodsp` always (DSP48E1 partial support in openXC7)

## Flash (no sudo)

```bash
# Requires FTDINoSerial.kext loaded BEFORE USB enumeration
python3 hardware/tools/trinity_flash.py <bitstream>

# If "no device found": kext lost claim after USB replug
# Fix: physical unplug → replug → daemon reloads kext
python3 /usr/bin/kmutil load -p /Library/Extensions/FTDINoSerial.kext
```

## Bitstream Provenance (NEW)

```bash
# Before flashing, ALWAYS generate provenance manifest:
python3 hardware/tools/bitstream_provenance.py generate \
  fpga/openxc7-synth/${DESIGN}.v fpga/openxc7-synth/gf_adder_param.v \
  --design ${DESIGN} --bit ${DESIGN}.bit

# Verify before flash:
python3 hardware/tools/bitstream_provenance.py verify ${DESIGN}.bit
```

## Conformance Testing

```bash
# Narrow formats (GF4-GF32):
python3 conformance/gf_conformance.py --port /dev/cu.usbserial-1120 --fmt gf16 --op add

# Wide formats (GF64+):
python3 conformance/gf_wide_conformance.py --port /dev/cu.usbserial-1120 --fmt gf64 --op add --delay 0.3

# Oracle (exact Fraction arithmetic):
python3 -c "from conformance.gf_ref import gf_add, FORMATS; ..."
```

## LESSONS LEARNED (auditor-verified)

1. **HAS_INF is per-format, not universal.** Only GF16 has Inf/NaN (exp=all-ones reserved). All other GF formats (including GF64/128/256) treat exp=all-ones as finite max value. Fifteen GF64+ RTL wrappers had HAS_INF(1) — fixed to HAS_INF(0) in Wave 2026-07-14.

2. **cur_byte must be `reg` not `wire`.** Verilog error: assigning in `always @(*)` requires `reg`. The GF64 wrapper had this bug — the previously flashed bitstream was from unknown source. Always verify source compiles before trust.

3. **iverilog is the fast verification gate.** Python bit-model (verify_adder_e24.py) transcribes RTL exactly. 1544/1544 bit-exact for GF64 E=24/M=39. Then iverilog inline TB (tb_gf64_inline.v) confirms 9/9 edge cases in seconds.

4. **Timing is NOT the cause of wide-format discrepancies.** Tested with 0.3s delay — same result. Root cause was HAS_INF mismatch + cur_byte compile bug.

5. **Always check provenance before flashing.** Use bitstream_provenance.py generate+verify. 30+ orphan bitstreams in /tmp have zero provenance.

6. **Scientific positioning (2026-07-14 literature scan):**
   - Trinity's moat = "format catalog × open-source-silicon proof" (83 formats on openXC7)
   - GoldenFloat φ-ratio = design heuristic, NOT a numerical theorem
   - Tekum (2512.10964) collides with ternary+float thesis — read before claiming novelty
   - ELiTeFormer (2607.03652) = nearest HSLM-on-FPGA competitor
   - DePIN + reproducible openXC7 bitstream = strongest novel niche

## Key Files

| File | Purpose |
|------|---------|
| `fpga/openxc7-synth/gf_adder_param.v` | Parameterized GF adder (E/M configurable) |
| `fpga/openxc7-synth/gf_mul_param.v` | Parameterized GF multiplier (DSP or LUT) |
| `conformance/gf_ref.py` | Golden oracle (Fraction-exact, RNE rounding) |
| `conformance/verify_adder_e24.py` | Python bit-model of gf_adder_param core |
| `conformance/tb_gf64_inline.v` | iverilog testbench for GF64 edge cases |
| `hardware/tools/bitstream_provenance.py` | Source→bit SHA256 binding |
| `hardware/tools/trinity_flash.py` | No-sudo flash client |
| `research/LITERATURE_SCAN_2024_2026.md` | 6-axis paper scan (40+ arXiv IDs) |
| `research/CATALOG_PAPER_OUTLINE.md` | cs.AR paper outline |
| `research/GOLDENFLOAT_VS_TEKUM.md` | Urgent comparison vs tekum |
