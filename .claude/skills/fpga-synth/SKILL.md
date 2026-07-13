---
name: fpga-synth
description: Synthesize Verilog to bitstream for AX7203 via openXC7 Docker, flash via JTAG. Use for any FPGA synthesis, flashing, or board experimentation.
argument-hint: <design-name or "experience" to read logs>
allowed-tools: Bash(docker *), Bash(cargo *), Bash(curl *), Bash(ls *), Read, Grep, Glob, Write, Edit, WebFetch
---

# FPGA Synthesis + Flash Pipeline

## Compute-HW Catalog (452+ families, 10 ops, 5 parametric cores)

### Tier-E Verified on Silicon (2026-07-13)
| Format | Op | Vectors | Result |
|--------|-----|---------|--------|
| GF4 | ADD | 256/256 | bit-exact |
| GF4 | MUL | 256/256 | bit-exact |
| GF8 | ADD | 512/512 | bit-exact |
| GF12 | ADD | 256/256 | bit-exact |
| GF16 | ADD | 128/128 | bit-exact |
**Total: 1408/1408 vectors, 0 failures. IDCODE: 0x13636093.**

### openXC7 Pipeline (PROVEN end-to-end)
```
yosys → nextpnr-xilinx (--fasm) → fasm2frames → xc7frames2bit (--part.yaml) → pld load → UART
```

### Flash Without Sudo
```bash
python3 hardware/tools/trinity_flash.py /path/to/design.bit
python3 hardware/tools/trinity_flash.py --scan
```

### Build Bitstream via CI
```bash
gh api repos/gHashTag/trinity-fpga/actions/workflows/build-ax7203-bitstream.yml/dispatches \
  -f 'ref=main' -f 'inputs[design]=corona_compute_gf16_add_ax7203'
# Download when done:
gh run download <run_id>
```

### Conformance
```bash
python3 -c "
import sys; sys.path.insert(0, 'conformance')
from gf_ref import FORMATS, gf_add
# ... UART test against Fraction-exact golden oracle
"
```

### trios-fpga CLI (Rust)
```bash
cargo run --manifest-path rings/BR-BITSTREAM/Cargo.toml -- flash-openocd --bitstream <file.bit>
cargo run --manifest-path rings/BR-BITSTREAM/Cargo.toml -- synth --rtl-dir <dir> --constraints <xdc>
cargo run --manifest-path rings/BR-BITSTREAM/Cargo.toml -- status-openocd
```

### Critical Fixes Applied
- `reg [9:0] rxcnt` (was [8:0], overflow at BAUD_DIV+BAUD_DIV>>1=651)
- `xc7frames2bit --part.yaml` (YAML format, not JSON)
- `nextpnr --fasm` (not `--write` which outputs JSON)
- FTDINoSerial.kext (codeless kext, IOProbeScore=90000, requires csrutil enable --without kext)
