---
name: fpga-synth
description: "AX7203 openXC7. 16 Tier-E 4/4 proven. HAS_INF fixed. Tekum oracle. Benchmark done. DePIN attestation. Catalog paper draft ready."
allowed-tools: Bash(docker *), Bash(ls *), Read, Grep, Glob, Write, Edit
---

# FPGA Pipeline — AX7203 XC7A200T

## Current State (2026-07-14, 3 waves complete)

| Axis | Count | Detail |
|------|-------|--------|
| SW-bitexact | 75/83 | Ceiling reached (8 structural terminal) |
| decode-HW Tier-E | ~47 unique | Ceiling 71 — biggest remaining gap |
| compute-HW Tier-E | 16 cells | GF4-GF32 × {ADD,MUL}, 11392/11392 bit-exact |
| GF64+ | HAS_INF fixed | Bitstreams rebuilt, awaiting re-flash |
| Tekum | Oracle + decode RTL | tekum8/16/32, self-test PASS |
| Benchmark | 7 formats compared | GF16 competitive with Posit16/FP16 |
| DePIN | Attestation protocol | Reproducible build + Ed25519 attestation |

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
- `-nocarry` always | `-nodsp` always (openXC7 partial DSP)

## Flash (no sudo)

```bash
python3 hardware/tools/trinity_flash.py <bitstream>
# If "no device found": physical unplug → replug → kmutil load kext
```

## Bitstream Provenance (MANDATORY before flash)

```bash
python3 hardware/tools/bitstream_provenance.py generate \
  <source.v> <adder.v> --design <name> --bit <bitstream.bit>
python3 hardware/tools/bitstream_provenance.py verify <bitstream.bit>
```

## Accuracy Benchmark Results (2026-07-14)

| Format | Arithmetic Mean Rel Err | Dynamic Range | LUT (Add) |
|--------|------------------------|---------------|-----------|
| FP16 | 1.30e-03 | 2.30e-04 | ~300 |
| Posit(16,1) | 1.36e-03 | 5.07e-03 | ~1500 |
| **GF16** | **1.63e-03** | **4.08e-04** | **118** |
| Takum16 | 2.13e-03 | 7.24e-04 | ~750 |
| GF12 | 5.14e-03 | 4.20e-01 | ~60 |
| BF16 | 5.14e-03 | 1.65e-03 | ~200 |
| MXFP8 | 7.10e-02 | 4.45e-01 | N/A |

GF16: competitive accuracy at 12.7x lower LUT cost than Posit16.

## LESSONS LEARNED (all auditor-verified)

1. **HAS_INF is per-format.** Only GF16 has Inf/NaN. Fifteen GF64+ wrappers had HAS_INF(1) — all fixed to HAS_INF(0).
2. **cur_byte must be `reg`** in always@(*). Provenance gap = flashed from unknown source.
3. **iverilog is the fast verification gate.** Python bit-model (1544/1544) + iverilog (9/9) = confident before silicon.
4. **Timing is NOT the cause** of wide-format discrepancies. Root cause = HAS_INF + cur_byte.
5. **Provenance before every flash.** bitstream_provenance.py generate+verify.
6. **Trinity's moat** = "format catalog × open-source-silicon proof" — nobody else proves 83 formats on openXC7.
7. **Tekum (2512.10964)** = nearest intellectual competitor. Read before claiming ternary-float novelty.
8. **DePIN + reproducible openXC7** = strongest novel niche. Bitstream hash = trust anchor.

## Key Files

| File | Purpose |
|------|---------|
| `fpga/openxc7-synth/gf_adder_param.v` | Parameterized GF adder |
| `conformance/gf_ref.py` | Golden oracle (Fraction-exact) |
| `conformance/tekum_ref.py` | Tekum oracle (tapered precision) |
| `conformance/verify_adder_e24.py` | Python bit-model of adder core |
| `hardware/tools/bitstream_provenance.py` | Source→bit SHA256 binding |
| `src/trinity_node/attestation.zig` | DePIN attestation (Ed25519) |
| `deploy/reproducible/Dockerfile.openxc7-pinned` | Reproducible build image |
| `deploy/contracts/ATTESTATION_PROTOCOL.md` | Attestation protocol spec |
| `research/format_benchmark.py` | Head-to-head accuracy tool |
| `research/CATALOG_PAPER_DRAFT.md` | ~3750-word paper draft |
| `research/LITERATURE_SCAN_2024_2026.md` | 6-axis paper scan |
| `research/GOLDENFLOAT_VS_TEKUM.md` | GF vs tekum comparison |
