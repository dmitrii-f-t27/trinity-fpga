# EXPERIENCE: ALINX AX7203 Blinky Bring-Up via openXC7 on GitHub Actions
Date: 2026-06-24
Board: ALINX AX7203 (Artix-7 XC7A200T-FBG484-2, speed grade -2)
Host: GitHub Actions ubuntu-latest x86_64 runner
Flash target: Local macOS host via OpenOCD + AL321 FT2232H USB-JTAG cable

## Goal
Generate a valid `blinky_ax7203.bit` for the new AX7203 carrier board and confirm
DONE lights / LEDs blink after flashing.

## Trinity FPGA Hardware Inventory
These ALINX devices are available in the project. Google Drive documentation links are canonical.

| Device | Type | Docs |
|--------|------|------|
| AX7203 / AX7203B | ALINX Artix-7 FPGA carrier board (XC7A200T-FBG484-2) | [AX7203/AX7203B_EN](https://drive.google.com/drive/folders/1u5Ofz0sWViA-ROgPr4fEx6Iz3zJhJmcK?usp=sharing) |
| P201 MINI / P203 MINI | ALINX FPGA modules / daughter cards | [P201 MINI / P203 MINI](https://drive.google.com/drive/folders/1mKWlSyf95ehVl2OCfvKzC0WvL2Q04cEy?usp=sharing) |
| AN9767 | ALINX module | [AN9767 docs](https://drive.google.com/drive/folders/10egsCPDlaWmdaQDXNscolcV2tigygh-I?usp=sharing) |
| AN706 | ALINX module | [AN706 docs](https://drive.google.com/drive/folders/1mqM_hEX_7Zeqsh6EUpAWaqTaayQ3_vhV?usp=sharing) |
| AN9238 | ALINX module | [AN9238 docs](https://drive.google.com/drive/folders/17AVfY9cxfJg1s2b3_iEUXuupqfuhz3tV?usp=sharing) |
| AN5642 | ALINX module | [AN5642 docs](https://drive.google.com/drive/folders/1u6TrdFFbF9tGKWl8597npVKh9QQu9T_v?usp=sharing) |
| AN430 | ALINX module | [AN430 docs](https://drive.google.com/drive/folders/1KjpP-1FKpjwGo0igNBqTSptd4BN0bS7k?usp=sharing) |

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
| 28096964681 | cache + router1 + 100 MHz | ✅ success | `--router router1` + `--timing-allow-fail` bypassed GND_WIRE bug |

## Known Blockers / Open Issues

1. **nextpnr-xilinx GND_WIRE bug on xc7a200t (RESOLVED for blinky)**
   - Router2 fails with `Invalid global constant node 'INT_L_X0Y105/GND_WIRE'`.
   - Workaround: use `--router router1 --timing-allow-fail --freq 100.0`.

2. **Timing at 200 MHz**
   - Pure counter on 200 MHz reports ~87.6 MHz max. For blinky this does not matter,
     but full VSA/GF16 designs will need PLL/MMCM.

3. **fasm2frames antlr warning**
   - Slow pure-Python parser fallback; not fatal but slows bitstream assembly.

### GF16 Conformance Diagnostic (2026-06-24)

| Attempt | Design size | nextpnr flags | Result | Notes |
|---------|-------------|---------------|--------|-------|
| 28100283541 | full ALU (ADD+MUL) + DSP48E1 | `--placer sa --router router1` | hung >1h | DSP48E1 placer/router convergence issue on xc7a200t |
| 28102591254 | ADD only, LUT-based, 128 LC | `--placer sa --router router1` | hung >1h | Router1 also very slow on xc7a200t; design had CARRY4 chains |

### Diagnostic learnings
- `nextpnr-xilinx` Router2 is known to fail to converge on XC7A100/XC7A200 ([gatecat/nextpnr-xilinx#83](https://github.com/gatecat/nextpnr-xilinx/issues/83)).
- Long `CARRY4` chains can hang the HeAP or SA placer ([gatecat/nextpnr-xilinx#34](https://github.com/gatecat/nextpnr-xilinx/issues/34)); workaround is `synth_xilinx -nocarry`.
- `--timing-allow-fail --force` skips timing errors but not routing/placer convergence.
- `--verbose-placer 10 --verbose-router 10` enables progress output in nextpnr logs.
- `--freq 50.0` reduces routing stress vs 100 MHz / 200 MHz.

### Applied fixes
- Switched to `synth_xilinx -nocarry` in GF16 workflow.
- Reduced target frequency to 50 MHz.
- Added verbose logging and tail/grep of nextpnr log for diagnostics.

## Flash Result (2026-06-24)

Bitstream: `build/ax7203_blinky/blinky_ax7203.bit` (9.3 MB, valid Xilinx BIT for xc7a200tfbg484-2)

### Attempt 1 (FAILED: DONE dark, LEDs not blinking)
```bash
openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
  -c "init" \
  -c "pld load 0 build/ax7203_blinky/blinky_ax7203.bit" \
  -c "xc7_program xc7.tap" \
  -c "shutdown"
```
OpenOCD status: IDCODE `0x13636093` confirmed, no JTAG error.
Hardware observation: DONE not lit, LED0–LED3 not blinking.

### Attempt 2 (corrected sequence)
Updated `ax7203_al321.cfg`:
- Removed `JSTART` from `xc7_program`
- Recommended usage is `pld load` + `runtest 200000` + `shutdown`

```bash
openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
  -c "init" \
  -c "pld load 0 build/ax7203_blinky/blinky_ax7203.bit" \
  -c "runtest 200000" \
  -c "shutdown"
```
Hardware observation: DONE lit ✅, but LED0–LED3 are steady ON and not blinking.

### Hypothesis for steady LEDs
Counter clock does not reach the flip-flops. Design used `IBUFDS` output directly
as the clock net without a `BUFG` global clock buffer. On Xilinx 7-series,
clocks sourced from differential pads normally go `IBUFDS → BUFG`. Without
`BUFG`, nextpnr may route the clock on general fabric and the counter may not
toggle, leaving high counter bits at a constant value and LEDs constantly on.

### Attempt 3 (SUCCESS)
Updated `fpga/vivado/blinky_ax7203.v` to insert `BUFG` between `IBUFDS` and
the counter clock net. Synthesized via workflow **28099101503** (success).

Flashed with:
```bash
openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
  -c "init" \
  -c "pld load 0 build/ax7203_blinky/blinky_ax7203.bit" \
  -c "runtest 200000" \
  -c "shutdown"
```

Hardware observation:
- DONE lit ✅
- LED0–LED3 blinking ✅
- Power indicators PWR3V3 / PWR1V8 / PWR1V0 lit steadily (normal)
- INIT may remain dimly lit (normal on this carrier)

## Result
AX7203 minimal blinky bring-up is **complete**.

## Next Steps
1. Proceed to variant B: GF16 codec + bit-exact conformance over UART.
2. Create `fpga/vivado/gf16_codec_ax7203.v` + XDC.
3. Host script `conformance/gf16_conformance_ax7203.py`.
4. Synthesize, flash, run conformance.
