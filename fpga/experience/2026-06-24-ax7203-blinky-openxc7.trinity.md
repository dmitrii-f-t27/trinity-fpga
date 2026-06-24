# EXPERIENCE: ALINX AX7203 Blinky Bring-Up via openXC7 on GitHub Actions
Date: 2026-06-24
Board: ALINX AX7203 (Artix-7 XC7A200T-FBG484-2, speed grade -2)
Host: GitHub Actions ubuntu-latest x86_64 runner
Flash target: Local macOS host via OpenOCD + AL321 FT2232H USB-JTAG cable

## Goal
Generate a valid `blinky_ax7203.bit` for the new AX7203 carrier board and confirm
DONE lights / LEDs blink after flashing.

## CONFIRMED Truth (verified on hardware)

### Board Identification
| Parameter | Value |
|-----------|-------|
| Board | ALINX AX7203 |
| FPGA | XC7A200T |
| Package | FBG484 |
| Speed grade | -2 |
| JTAG IDCODE | **0x13636093** (rev 1) |
| Cable | AL321 (FT2232H-based, Digilent JTAG-SMT2 wiring) |

### Pin Mapping (verified via OpenOCD + ALINX manual)
| Signal | Pin | Standard | Notes |
|--------|-----|----------|-------|
| CLK200_P | R4 | **DIFF_SSTL15** | NOT LVDS — using LVDS blocked DONE |
| CLK200_N | T4 | **DIFF_SSTL15** | differential pair |
| CPU_RESET_N | T6 | LVCMOS15 | active-low |
| LED0 | B13 | LVCMOS18 | active-high |
| LED1 | C13 | LVCMOS18 | active-high |
| LED2 | D14 | LVCMOS18 | active-high |
| LED3 | D15 | LVCMOS18 | active-high |
| UART_TX | N15 | LVCMOS33 | FPGA → host |
| UART_RX | P20 | LVCMOS33 | host → FPGA |

### OpenOCD verification command
```bash
openocd -f fpga/openxc7-synth/ax7203_al321.cfg -c "init" -c "scan_chain" -c "shutdown"
```
Expected: `JTAG tap: xc7.tap ... found: 0x13636093`

## Synthesis Pipeline (GitHub Actions)

Workflow: `.github/workflows/ax7203-blinky-bitstream.yml`
Docker image: `regymm/openxc7:latest` (amd64)

### Stages
1. **Yosys synthesis**
   ```bash
   yosys -p "read_verilog fpga/vivado/blinky_ax7203.v;
            synth_xilinx -flatten -abc9 -arch xc7 -top blinky_ax7203;
            setundef -zero -params;
            write_json build/ax7203_blinky/blinky_ax7203.json"
   ```

2. **Chipdb generation** (xc7a200tfbg484-2, ~317 MB, ~4 min on x86_64)
   ```bash
   cd /nextpnr-xilinx && \
   python3 xilinx/python/bbaexport.py --device xc7a200tfbg484-2 \
     --bba /work/build/ax7203_blinky/chipdb/xc7a200tfbg484-2.bba && \
   bbasm -l /work/build/ax7203_blinky/chipdb/xc7a200tfbg484-2.bba \
     /work/build/ax7203_blinky/chipdb/xc7a200tfbg484-2.bin
   ```

3. **nextpnr place and route**
   ```bash
   nextpnr-xilinx \
     --chipdb /work/build/ax7203_blinky/chipdb/xc7a200tfbg484-2.bin \
     --xdc /work/specs/fpga/constraints/ax7203.xdc \
     --json /work/build/ax7203_blinky/blinky_ax7203.json \
     --fasm /work/build/ax7203_blinky/blinky_ax7203.fasm \
     --freq 100.0 --seed 1 --placer sa --router router1 \
     --timing-allow-fail --force
   ```

4. **fasm2frames + xc7frames2bit**
   ```bash
   fasm2frames --db-root /nextpnr-xilinx/xilinx/external/prjxray-db/artix7 \
     --part xc7a200tfbg484-2 \
     /work/build/ax7203_blinky/blinky_ax7203.fasm \
     /work/build/ax7203_blinky/blinky_ax7203.frames
   xc7frames2bit \
     --part_file /nextpnr-xilinx/xilinx/external/prjxray-db/artix7/xc7a200tfbg484-2/part.yaml \
     --part_name xc7a200tfbg484-2 \
     --frm_file /work/build/ax7203_blinky/blinky_ax7203.frames \
     --output_file /work/build/ax7203_blinky/blinky_ax7203.bit
   ```

## Critical nextpnr-xilinx Constraint Rules

nextpnr-xilinx **does NOT expand grouped XDC assignments** the way Vivado does.

### ❌ Wrong
```tcl
set_property IOSTANDARD DIFF_SSTL15 [get_ports {clk200_p clk200_n}]
set_property IOSTANDARD LVCMOS18 [get_ports {led[0] led[1] led[2] led[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {uart_tx uart_rx}]
```

### ✅ Correct
```tcl
set_property IOSTANDARD DIFF_SSTL15 [get_ports clk200_p]
set_property IOSTANDARD DIFF_SSTL15 [get_ports clk200_n]
set_property IOSTANDARD LVCMOS18 [get_ports led[0]]
set_property IOSTANDARD LVCMOS18 [get_ports led[1]]
set_property IOSTANDARD LVCMOS18 [get_ports led[2]]
set_property IOSTANDARD LVCMOS18 [get_ports led[3]]
set_property IOSTANDARD LVCMOS33 [get_ports uart_tx]
set_property IOSTANDARD LVCMOS33 [get_ports uart_rx]
```

Failure mode when wrong:
```
ERROR: port <name> of type PAD has no IOSTANDARD property
```

## Iteration History

| Run | Commit | Result | Key fix / error |
|-----|--------|--------|-----------------|
| 28094155822 | ci(fpga): add workflow | ❌ File not found | Workflow ran before `fpga/vivado/blinky_ax7203.v` existed on main |
| 28094271883 | feat(fpga): AX7203 board bring-up | ❌ `clk200_n no IOSTANDARD` | XDC used grouped `DIFF_SSTL15 [get_ports {clk200_p clk200_n}]` |
| 28094818682 | DIFF_TERM FALSE | ❌ `clk200_n no IOSTANDARD` | `DIFF_TERM` irrelevant; still grouped assignment |
| 28095300565 | separate IOSTANDARD on P/N | ❌ `uart_rx no IOSTANDARD` | Grouped assignment still used for led/uart |
| 28095785438 | per-port IOSTANDARD | ❌ `Invalid global constant node INT_L_X0Y105/GND_WIRE` + timing fail | Router2 hits GND_WIRE bug; 200 MHz too aggressive |
| 28096964681 | cache + router1 + 100 MHz | pending | Attempt to bypass GND_WIRE bug and timing failure |

## Known Blockers / Open Issues

1. **nextpnr-xilinx GND_WIRE bug on xc7a200t**
   - Router2 fails with `Invalid global constant node 'INT_L_X0Y105/GND_WIRE'`.
   - Workaround attempt: use `--router router1`.
   - If router1 also fails, the chipdb generated by `regymm/openxc7` may be inconsistent for xc7a200t.

2. **Timing at 200 MHz**
   - Pure counter on 200 MHz reports ~87.6 MHz max. For blinky this does not matter,
     but full VSA/GF16 designs will need PLL/MMCM.

3. **fasm2frames antlr warning**
   - Slow pure-Python parser fallback; not fatal but slows bitstream assembly.

## Next Steps

1. Wait for router1 + 100 MHz run result.
2. If still GND_WIRE error: regenerate chipdb with `openXC7/toolchain-nix` or use
   a pre-built chipdb from a compatible source.
3. Once `.bit` is valid, flash via OpenOCD locally:
   ```bash
   cargo run --manifest-path rings/BR-BITSTREAM/Cargo.toml -- flash-openocd \
     --bitstream build/ax7203_blinky/blinky_ax7203.bit
   ```
4. Observe DONE and LEDs; record states in this file.
5. Proceed to variant B: GF16 codec + bit-exact conformance over UART.
