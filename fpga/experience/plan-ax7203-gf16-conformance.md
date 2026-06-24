# Plan: Variant B — GF16 Codec + Bit-Exact Conformance on AX7203

## Goal
Build, synthesize, and run a GoldenFloat16 (GF16) codec + bit-exact conformance test on the ALINX AX7203 (XC7A200T-FBG484-2) over USB-UART (N15 TX / P20 RX).

## Phases

### Phase 1 — Read Input Specs (1 iteration)
- Read GoldenFloat16 spec (`specs/gf16/*.tri` or `external/zig-golden-float` docs).
- Read `conformance/gf16_conformance_ax7203.py` if it exists.
- Extract: exact bit patterns, operations under test, expected host-side reference outputs.

### Phase 2 — Verilog Design (1–2 iterations)
Files to create:
- `fpga/vivado/gf16_codec_ax7203.v` — top module
  - `IBUFDS` on clk200_p/n
  - Synchronous reset from `rst_n` (active-low)
  - UART TX engine (115200 8N1) on `uart_tx`
  - GF16 codec modules from spec or hand-rolled minimal version
  - State machine streaming test vectors and results
- `specs/fpga/constraints/gf16_ax7203.xdc` — reuse `ax7203.xdc` pinout

Key constraints:
- 200 MHz clock → use PLL/MMCM to generate UART clock and core clock
- IOSTANDARD per-port only (DIFF_SSTL15 on P/N, LVCMOS18 LEDs, LVCMOS33 UART)
- `--router router1 --timing-allow-fail` until GND_WIRE bug fixed

### Phase 3 — Synthesis + Bitstream (1–2 iterations)
- Extend `.github/workflows/ax7203-blinky-bitstream.yml` or create `ax7203-gf16-conformance.yml`.
- Cache xc7a200tfbg484-2 chipdb.
- Build bitstream, upload artifact.

### Phase 4 — Host Software
- Python script `conformance/gf16_conformance_ax7203.py` to:
  - Open USB-UART
  - Send seed / test vector
  - Receive GF16 result from FPGA
  - Compare against host GoldenFloat16 reference
  - Report pass/fail per operation and bit-exact count

### Phase 5 — Flash + Run on Hardware
- Flash via OpenOCD + AL321.
- Run host conformance script.
- Capture LED/uart_tx behavior.
- Iterate if any mismatch.

### Phase 6 — Document
- Update `fpga/experience/2026-06-24-ax7203-blinky-openxc7.trinity.md` or create new `2026-06-24-ax7203-gf16-conformance.trinity.md`.
- Update SKILL.md with GF16-on-AX7203 commands.

## Success Criteria
- [ ] `gf16_codec_ax7203.bit` builds in GitHub Actions.
- [ ] Bitstream flashes and DONE lights.
- [ ] Host script connects over USB-UART.
- [ ] ≥1 GF16 operation passes bit-exact comparison against reference.
- [ ] Experience log and SKILL.md updated.

## Blockers to Watch
- PLL/MMCM placement on xc7a200t with openXC7.
- Timing closure for codec logic at target frequency.
- fasm2frames / chipdb OOM if not cached.
- OpenOCD UART bridge reliability at 115200.

## Next Action
Create the Verilog top and XDC; trigger synthesis workflow.
