---
name: fpga-synth
description: Synthesize Verilog to bitstream for QMTECH XC7A100T or ALINX AX7203 via openXC7 Docker, flash via ESP32 XVC. Use for any FPGA synthesis, flashing, or board experimentation.
argument-hint: <design-name or "experience" to read logs>
allowed-tools: Bash(docker *), Bash(cargo *), Bash(curl *), Bash(ls *), Read, Grep, Glob, Write, Edit, WebFetch
---

# FPGA Synthesis + Flash Pipeline

## Compute-HW Catalog (440 families, 10 ops)
- **440 format families** × 10 operations (add/mul/div/sqrt/quire/fma/cmp/alu/to_fp32/fp32_to)
- **5 parametric cores**: gf_adder_param(410 LUT), gf_mul_param(294 LUT+1 DSP), gf_div_param(210 LUT), gf_sqrt_param(131 LUT+8 DSP), gf_quire_param(75 LUT)
- **Full bit-width coverage 3-128** with ≥2 E/M variants per width
- **16,640 conformance vectors** in `conformance/vectors/`
- **SW conformance**: `python3 conformance/gen_sw_conformance.py` (25/25 PASS)
- **HW conformance**: `sudo bash conformance/hw_silicon_sprint.sh` (needs sudo + board)
- **Catalog manifest**: `docs/catalog_manifest.json` (machine-readable index)
- **Paper materials**: `docs/arxiv_v2_table.tex`, `docs/arxiv_v2_comparison.md`

### Silicon Sprint (HW verification)
```bash
# Prep: check bitstream availability
bash conformance/prep_silicon_sprint.sh

# Full sprint: decode 77 + compute 25
sudo bash conformance/hw_silicon_sprint.sh

# Single format/op conformance
python3 conformance/compute_conformance_template.py --port /dev/cu.usbserial-1120 --fmt gf16 --op div
```

### FTDI MPSSE Fix (macOS)
AppleSerialShim kext blocks FTDI MPSSE for large JTAG transfers. Fix:
```bash
sudo kextunload -b com.apple.driver.AppleSerialShim   # before flash
sudo kextload -b com.apple.driver.AppleSerialShim      # after flash (for UART)
```

Supported boards:
- **QMTECH XC7A100T-FGG676** (legacy)
- **ALINX AX7203 (XC7A200T-FBG484-2)** — new primary target

## Trinity FPGA Hardware Inventory
These devices are available in the project. Documentation links are canonical; replace `YOUR_FOLDER_ID` with the actual Google Drive folder IDs shared by the user.

| Device | Type | Docs / Notes |
|--------|------|--------------|
| **AX7203 / AX7203B** | ALINX Artix-7 FPGA carrier board | [AX7203/AX7203B_EN](https://drive.google.com/drive/folders/1u5Ofz0sWViA-ROgPr4fEx6Iz3zJhJmcK?usp=sharing) |
| **P201 MINI / P203 MINI** | ALINX FPGA modules / daughter cards | [P201 MINI / P203 MINI](https://drive.google.com/drive/folders/1mKWlSyf95ehVl2OCfvKzC0WvL2Q04cEy?usp=sharing) |
| **AN9767** | ALINX module | [AN9767 docs](https://drive.google.com/drive/folders/10egsCPDlaWmdaQDXNscolcV2tigygh-I?usp=sharing) |
| **AN706** | ALINX module | [AN706 docs](https://drive.google.com/drive/folders/1mqM_hEX_7Zeqsh6EUpAWaqTaayQ3_vhV?usp=sharing) |
| **AN9238** | ALINX module | [AN9238 docs](https://drive.google.com/drive/folders/17AVfY9cxfJg1s2b3_iEUXuupqfuhz3tV?usp=sharing) |
| **AN5642** | ALINX module | [AN5642 docs](https://drive.google.com/drive/folders/1u6TrdFFbF9tGKWl8597npVKh9QQu9T_v?usp=sharing) |
| **AN430** | ALINX module | [AN430 docs](https://drive.google.com/drive/folders/1KjpP-1FKpjwGo0igNBqTSptd4BN0bS7k?usp=sharing) |

When designing for these modules, extract pinout and voltage level info from the linked manuals and update this SKILL + the board XDC accordingly.

## BEFORE STARTING: Load Experience
Read the experience log FIRST to avoid repeating work:
- Primary: `fpga/experience/2026-06-24-ax7203-blinky-openxc7.trinity.md`
- Legacy QMTECH: `fpga/experience/2026-05-07-led-mapping-synthesis-flash.trinity.md`

Always check `fpga/experience/*.trinity.md` for latest AX7203 entry and update it after every experiment.

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

### IMPORTANT: xc7a200t chipdb
- Generating `xc7a200tfbg484-2.bin` via `bbaexport.py` inside Docker/QEMU on ARM Mac
  was killed at 16 GB RAM (OOM). Use x86_64 Linux or GitHub Actions.
- In CI, cache the chipdb with `actions/cache@v4` to avoid regenerating it every run.
- Known issue with `regymm/openxc7` on xc7a200t: `Invalid global constant node 'INT_L_X0Y105/GND_WIRE'`.
  Workaround attempt: `--router router1 --timing-allow-fail --freq 100.0`.

Until the chipdb + routing are stable, the openXC7 bitstream path may be blocked.
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
  -c 'pld load 0 build/ax7203_blinky/blinky_ax7203.bit' \
  -c 'runtest 200000' \
  -c 'shutdown'
```

**IMPORTANT**: do NOT call `xc7_program` after `pld load`. The `virtex2` driver
already sends the 7-series start-up sequence. Re-issuing `JSTART` can leave
the FPGA outside user mode (DONE stays dark). The `xc7_program` proc in the
cfg is only for explicit clear/reset before loading.

Confirmed (2026-06-24):
- Workflow `28096964681` succeeded → `blinky_ax7203.bit` (9.3 MB)
- Flash command completed without JTAG errors
- IDCODE verified: `0x13636093` (Artix-7 XC7A200T rev 1)
- `runtest 200000` provides extra TCK start-up cycles

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

## Tier-E Silicon Proof (2026-07-13)

### Verified Formats (UART conformance on AX7203)
| Format | Op | Vectors | Result | SHA256 (first 12) |
|--------|-----|---------|--------|-------------------|
| GF4 | ADD | 256/256 exhaustive | bit-exact | 4c7b1e59a964 |
| GF8 | ADD | 512/512 | bit-exact | ca79919948f1 |
| GF16 | ADD | 128/128 | bit-exact | 925cc793a0de |

**Total: 896/896 vectors, 0 failures. IDCODE: 0x13636093.**

### openXC7 Full Pipeline (PROVEN)
```
yosys (synth_xilinx -abc9 -nocarry -arch xc7)
  → nextpnr-xilinx (--fasm, --router router1, --timing-allow-fail, --freq 10)
    → fasm2frames (--db-root prjxray-db/artix7 --part xc7a200tfbg484-2)
      → xc7frames2bit (--part.yaml, --frm_file, --output_file)
        → pld load (openocd 500kHz, 156s via trinity_flashed daemon)
          → UART conformance (gf_ref.py Fraction-exact golden oracle)
```

### Critical Bug Fixed
`reg [8:0] rxcnt` → `reg [9:0] rxcnt` in 3200 compute modules.
BAUD_DIV + (BAUD_DIV>>1) = 651 > 511 (9-bit overflow).
Root cause of UART silence in all compute modules.

### Flash Without Sudo
```bash
# One-time install
python3 hardware/tools/trinity_flashed.py --install
sudo cp /tmp/com.trinity.flashed.plist /Library/LaunchDaemons/
sudo launchctl load /Library/LaunchDaemons/com.trinity.flashed.plist

# Flash (no sudo needed)
python3 hardware/tools/trinity_flash.py /path/to/design.bit
python3 hardware/tools/trinity_flash.py --scan
```

### FTDI MPSSE Fix
FTDINoSerial.kext (codeless kext, IOProbeScore=90000) prevents AppleSerialShim.
Requires: `csrutil enable --without kext` (Recovery Mode).
After USB replug: `kmutil load -p /Library/Extensions/FTDINoSerial.kext` via daemon.
