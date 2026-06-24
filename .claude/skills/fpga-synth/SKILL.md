---
name: fpga-synth
description: Synthesize Verilog to bitstream for QMTECH XC7A100T or ALINX AX7203 via openXC7 Docker, flash via ESP32 XVC. Use for any FPGA synthesis, flashing, or board experimentation.
argument-hint: <design-name or "experience" to read logs>
allowed-tools: Bash(docker *), Bash(cargo *), Bash(curl *), Bash(ls *), Read, Grep, Glob, Write, Edit, WebFetch
---

# FPGA Synthesis + Flash Pipeline

Supported boards:
- **QMTECH XC7A100T-FGG676** (legacy)
- **ALINX AX7203 (XC7A200T-FBG484-2)** — new primary target

## BEFORE STARTING: Load Experience
Read the experience log FIRST to avoid repeating work:
`fpga/experience/2026-05-07-led-mapping-synthesis-flash.trinity.md`

If the file doesn't exist, check `fpga/experience/*.trinity.md` for latest.

## ALINX AX7203 Board Truth (VERIFIED BY USER 2026-06-24)
| Signal | Pin | Standard | Notes |
|--------|-----|----------|-------|
| CLK200_P | R4 | DIFF_SSTL15 | 200 MHz differential (was LVDS — wrong, blocked DONE) |
| CLK200_N | T4 | DIFF_SSTL15 | 200 MHz differential (was LVDS — wrong, blocked DONE) |
| CPU_RESET_N | T6 | LVCMOS15 | Active-low reset |
| UART_TX | N15 | LVCMOS33 | FPGA -> host |
| UART_RX | P20 | LVCMOS33 | Host -> FPGA |
| LED0 | B13 | LVCMOS18 | Active-high |
| LED1 | C13 | LVCMOS18 | Active-high |
| LED2 | D14 | LVCMOS18 | Active-high |
| LED3 | D15 | LVCMOS18 | Active-high |

Clock input is **differential** — use `IBUFDS` in Verilog.
**IOSTANDARD must be `DIFF_SSTL15`**, not `LVDS`. Using `LVDS` caused DONE to stay dark and LEDs not to blink.
JTAG IDCODE (verified): **0x13636093** (XC7A200T rev 1).

## XDC Template (AX7203)
```tcl
set_property IOSTANDARD DIFF_SSTL15 [get_ports clk200_p]
set_property IOSTANDARD DIFF_SSTL15 [get_ports clk200_n]
set_property PACKAGE_PIN R4 [get_ports clk200_p]
set_property PACKAGE_PIN T4 [get_ports clk200_n]
create_clock -period 5.000 -name clk200 [get_ports clk200_p]

set_property IOSTANDARD LVCMOS15 [get_ports rst_n]
set_property PACKAGE_PIN T6 [get_ports rst_n]

set_property IOSTANDARD LVCMOS18 [get_ports led[0]]
set_property IOSTANDARD LVCMOS18 [get_ports led[1]]
set_property IOSTANDARD LVCMOS18 [get_ports led[2]]
set_property IOSTANDARD LVCMOS18 [get_ports led[3]]
set_property PACKAGE_PIN B13 [get_ports led[0]]
set_property PACKAGE_PIN C13 [get_ports led[1]]
set_property PACKAGE_PIN D14 [get_ports led[2]]
set_property PACKAGE_PIN D15 [get_ports led[3]]

set_property IOSTANDARD LVCMOS33 [get_ports uart_tx]
set_property IOSTANDARD LVCMOS33 [get_ports uart_rx]
set_property PACKAGE_PIN N15 [get_ports uart_tx]
set_property PACKAGE_PIN P20 [get_ports uart_rx]
```

## Synthesis Pipeline

Docker image: `regymm/openxc7` (amd64, needs QEMU on ARM Mac)
Chipdb generated per board/package/speedgrade.

### IMPORTANT: xc7a200t chipdb on ARM Mac
Generating `xc7a200tfbg484-2.bin` via `bbaexport.py` inside Docker/QEMU on ARM Mac
was killed at 16 GB RAM (OOM). Workarounds:
1. Generate chipdb on an x86_64 Linux host with >16 GB RAM and copy `.bin` to `build/ax7203_blinky/chipdb/`.
2. Use Vivado for bitstream generation (Vivado is not installed in this environment).
3. Request a pre-built `xc7a200tfbg484-2.bin` from the openXC7 project.

Until the chipdb is available, the openXC7 bitstream path is **blocked**.
The Verilog design is already yosys-lint-clean.

### AX7203 blinky synthesis command:
```bash
cargo run --manifest-path rings/BR-BITSTREAM/Cargo.toml -- synth \
  --rtl-dir fpga/vivado \
  --constraints specs/fpga/constraints/ax7203.xdc \
  --output-dir build/ax7203_blinky \
  --top blinky_ax7203
```

### Verify IDCODE via AL321 USB-JTAG / OpenOCD:
```bash
openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
  -c 'init' \
  -c 'scan_chain' \
  -c 'shutdown'
```
Expected output: `JTAG tap: xc7.tap ... found: 0x13636093`

### Flash bitstream via OpenOCD (temporary, until CLI supports AL321):
```bash
openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
  -c 'init' \
  -c 'xc7_program xc7.tap' \
  -c 'pld load 0 build/ax7203_blinky/blinky_ax7203.bit' \
  -c 'shutdown'
```

### Legacy XVC flash command (ESP32-XVC, if used):
```bash
cargo run --manifest-path rings/BR-BITSTREAM/Cargo.toml -- \
  --xvc-host 192.168.1.30 flash \
  --board AX7203 \
  --bitstream build/ax7203_blinky/blinky_ax7203.bit
```

### Docker tool paths (inside regymm/openxc7)
- Yosys: `/usr/local/bin/yosys`
- nextpnr-xilinx: `/usr/local/bin/nextpnr-xilinx`
- fasm2frames: `/prjxray/env/bin/fasm2frames`
- xc7frames2bit: `/usr/local/bin/xc7frames2bit`
- prjxray-db: `/nextpnr-xilinx/xilinx/external/prjxray-db/artix7`

### IMPORTANT fasm2frames flags
```bash
/prjxray/env/bin/fasm2frames \
  --db-root /nextpnr-xilinx/xilinx/external/prjxray-db/artix7 \
  --part xc7a200tfbg484-2 \
  input.fasm output.frames 2>/dev/null
```
Redirect stderr to /dev/null! Otherwise antlr warning gets mixed into frames file.
Use positional args (not stdout redirect) for clean output.

## Experimentation Protocol

### MANDATORY: After EVERY experiment iteration
1. Record result in experience file (timestamp, test name, pin states, LED states, done status)
2. Update the "Board Truth" section if new confirmed facts
3. Update "Open Issues" if new questions arise
4. Note synthesis warnings/errors

### Experiment cycle:
1. Read experience log
2. Design hypothesis
3. Create .v + .xdc in correct directory
4. Synthesize in Docker
5. Flash via ESP32 XVC
6. Ask user for LED observation
7. Record results in experience file
8. Iterate

## QMTECH Reference (legacy, for comparison — NOT our AX7203)
Source: github.com/ChinaQMTECH/QM_XC7A100T_WUKONG_BOARD
| Ver | Clock | LED0 | LED1 |
|-----|-------|------|------|
| V1 | M21 | ? | ? |
| V2 | M21 | V17 | V16 |
| V3 | M21 | G21 | G20 |

Our old board had LEDs on M22, R23, T23 — matches NONE of these.
Our new AX7203 board has LEDs on B13/C13/D14/D15.
