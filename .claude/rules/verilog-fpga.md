---
paths:
  - "fpga/**/*.v"
  - "fpga/**/*.xdc"
  - "openxc7-synth/**"
  - "specs/fpga/**/*.xdc"
---

# Verilog/FPGA Rules

## Before starting any FPGA work
1. Read the latest experience log in `fpga/experience/*.trinity.md`
   (currently `fpga/experience/2026-06-24-ax7203-blinky-openxc7.trinity.md`).
2. Read the skill `fpga-synth` (`.claude/skills/fpga-synth/SKILL.md`) for the
   current board truth, workflow, and known blockers.
3. Update the experience log after every experiment iteration with timestamp,
   test name, pin/LED states, DONE status, and synthesis errors.

## Source of truth
- Generate Verilog from `.tri` specs via `tri gen` pipeline when a spec exists.
- Direct `.v` edits are allowed only for board bring-up, test fixtures, and
  pipeline infrastructure.
- Never manually edit generated `.v` files in `var/trinity/output/fpga/`.

## XDC constraints (nextpnr-xilinx compatible)
- **Never** use grouped `set_property IOSTANDARD ... [get_ports {a b c}]` for
  nextpnr-xilinx. Assign each port individually:
  ```tcl
  set_property IOSTANDARD DIFF_SSTL15 [get_ports clk200_p]
  set_property IOSTANDARD DIFF_SSTL15 [get_ports clk200_n]
  ```
- Match the real board standard. For ALINX AX7203: `DIFF_SSTL15` on the
  differential clock (NOT `LVDS`).
- After modifying any `.xdc` or `.v`, run synthesis and record the result.

## Synthesis / flashing
- Preferred CI flow: GitHub Actions `.github/workflows/ax7203-blinky-bitstream.yml`
- Chipdb for `xc7a200tfbg484-2` should be cached in CI; regeneration takes ~4 min.
- Flash locally via OpenOCD + AL321 cable:
  ```bash
  cargo run --manifest-path rings/BR-BITSTREAM/Cargo.toml -- flash-openocd \
    --bitstream build/ax7203_blinky/blinky_ax7203.bit
  ```

## Code style
- Testbenches use `*_tb.v` suffix and `iverilog` for simulation.
- Keep modules under 500 lines; split into submodules if larger.
- Use parameterized widths — avoid hardcoded bit widths where possible.
- Clock domain crossings require explicit synchronizers.
