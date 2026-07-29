# JTAG on macOS ARM — Fixed Issues (2026-04-01)

## Hardware
- **Mac**: Apple Silicon (M1/M2/M3), macOS 14.x
- **Cable**: Xilinx DLC10 (clone)
- **FPGA**: QMTech XC7A100T-FGG676
- **Tools**: openFPGALoader, jtag_program (tri)

## Problems

### 1. DLC10 not detected on macOS ARM
```
❌ openFPGALoader --cable xpc
Error: FTDI: -3 (device not found)

❌ jtag_program flash bitstream.bit
Error: No JTAG cable found
```

**Cause**: FTDI drivers on macOS ARM have limitations with some clones.

### 2. fxload requires full Xcode
```bash
brew install kolontsov/fxload/fxload
# Error: xcode-select: error: tool 'xcodebuild' requires Xcode
```
fxload compiles from source and requires `xcodebuild` (full Xcode.app),
not just CommandLineTools.

### 3. USB Registry shows mismatched PIDs
```
system_profiler SPUSBDataType:
  FTDI   Vendor: 0x0403, Product: 0x6001 (bootloader)
  Xilinx  Vendor: 0x03fd, Product: 0x0013 (bootloader)
```
openFPGALoader looks for PID `0x0008` (JTAG mode), but the device
is stuck at PID `0x0013` (bootloader mode).

## Conclusion

**On the current Mac (Apple Silicon) it is IMPOSSIBLE to flash the FPGA via JTAG**:
- ❌ DLC10 clone — does not work
- ❌ openFPGALoader — does not see the cable
- ❌ jtag_program (tri) — does not see the cable

## Acceptable paths forward

| Option | Required | Status |
|---------|-----------|--------|
| **Linux PC/VM** | Separate Linux host | ✅ Reliable |
| **RP2040 bridge** | RP2040 + JTAG-bridge firmware | 🔄 Firmware needed |
| **SPI programmer** | CH341A and the like | 🔄 Adapter needed |
| **FTDI genuine** | Original Xilinx cable | ❌ Not guaranteed |

## Recommendation

For JTAG operations:
1. Use a separate Linux PC/laptop
2. Or set up a Linux VM with USB passthrough
3. UART debugging works — DSLogic U2basic ✅

## Experiments

| Date | Attempt | Result |
|------|---------|-----------|
| 2026-03-30 | jtag_program on Mac | FTDI -3 |
| 2026-03-31 | openFPGALoader --cable xpc | FTDI -3 |
| 2026-04-01 | fxload install | Requires Xcode (not just CLT) |
| 2026-04-01 | USB check | DLC10 stuck in PID 0x0013 (bootloader) |
| 2026-04-01 | fxload without sudo | 7962 bytes written, PID stuck 0x0013 |
| 2026-04-01 | fxload with sudo | 7962 bytes written, PID stuck 0x0013 |
| 2026-04-01 | openFPGALoader -c digilent | FTDI -3 |
| 2026-04-01 | cable reconnect | PID stays 0x0013 (no switch to 0x0008) |

## Agent Procedure for Mac (sudo-allowed for FPGA)

### Goal

1. Switch DLC10 cable to JTAG mode.
2. Give `openFPGALoader` access to it.
3. Flash a `.bit` bitstream.
4. Return system to normal state.

All steps documented in `.trinity/fpga/…` and updated manually only.

### Preconditions — mandatory check

```bash
# 1. Cable connected
system_profiler SPUSBDataType | grep -B2 -A3 "Xilinx"

# Expected:
# Vendor ID: 0x03fd (Xilinx Inc.)
# Product ID: 0x0013
```

If Vendor ID ≠ `0x03fd` — **STOP and page human.**

### Step 1 — Load firmware into DLC10 (with sudo)

```bash
cd /path/to/repo   # fpga/tools/fxload and xusb_xp2.hex are here

sudo ./fpga/tools/fxload -v -t fx2 -d 03fd:0013 -i fpga/tools/xusb_xp2.hex
```

Agent must:
- Ensure command finished **without ERROR**.
- Save log to `.trinity/logs/fxload-YYYYMMDD-HHMM.log` if needed.

### Step 2 — Replug cable

Physical action:
1. Unplug USB DLC10.
2. Wait 2–3 seconds.
3. Plug back in.

Verify:
```bash
system_profiler SPUSBDataType | grep -B2 -A3 "Xilinx"
```

- If Product ID still `0x0013` — **can proceed**, but note firmware is in RAM, PID didn't change.
- If becomes `0x0008` — FX2 is in JTAG mode (ideal case).

### Step 3 — Release FTDI for openFPGALoader (optional)

If `openFPGALoader` continues with `unable to open ftdi device: -3`:

```bash
sudo kextunload -b com.apple.driver.AppleUSBFTDI || true
```

Important: if «extension not found» — **ignore** (on newer macOS FTDI may be System Extension, not kext).

### Step 4 — Flash bitstream

```bash
openFPGALoader --detect

# if device found → flash:
openFPGALoader -c xilinx fpga/uart_bridge_j2.bit
```

Rules:
- If `--detect` doesn't see cable or FPGA — **DON'T continue**, log and page human.
- If flash succeeded, record in `.trinity/logs/openfpgaloader-YYYYMMDD-HHMM.log`.

### Step 5 — Restore system state

```bash
# Restore Apple FTDI driver (if exists)
sudo kextload -b com.apple.driver.AppleUSBFTDI || true

# Check UART cable
ls /dev/cu.usbserial* || true
```

### Safety invariants

Agent **has NO RIGHTS** to:
- Install new kext/drivers.
- Change SIP/Secure Boot.
- Run other `sudo` commands, except:

```bash
sudo ./fpga/tools/fxload -v -t fx2 -d 03fd:0013 -i fpga/tools/xusb_xp2.hex
sudo kextunload -b com.apple.driver.AppleUSBFTDI
sudo kextload  -b com.apple.driver.AppleUSBFTDI
```

Any list expansion — only after manual review.

### After flashing

1. Report **which .bit was flashed** and result.
2. Run test from Trinity: `tri fpga dslogic-uart`
3. Ask human to verify via DSLogic that UART patterns appear on CH0/CH1.

---

## Fix

```
status: WORKING (2026-04-01)
solution: fxload + replug + fxload + xc3sprog
discovery: fxload AFTER replug successfully switches PID to 0x0008
tool: xc3sprog (not openFPGALoader) supports xpc cable 0x03fd:0x0008
verified: FPGA XC7A100T detected, bitstream flashed successfully
agent-procedure: 2026-04-01 — documented above for sudo-capable Mac agents
```

### Working sequence (2026-04-01):

```bash
# 1. Load firmware (before replug)
sudo ./fpga/tools/fxload -v -t fx2 -d 03fd:0013 -i fpga/tools/xusb_xp2.hex

# 2. Physically replug DLC10 (unplug, wait 3 sec, plug in)

# 3. Load firmware again (CRITICAL: after replug!)
sudo ./fpga/tools/fxload -v -t fx2 -d 03fd:0013 -i fpga/tools/xusb_xp2.hex

# 4. Verify PID changed to 0x0008
system_profiler SPUSBDataType | grep "Product ID"

# 5. Flash bitstream
./fpga/tools/xc3sprog -c xpc <bitstream.bit>
```

### Experiments

| Date | Attempt | Result |
|------|---------|-----------|
| 2026-03-30 | jtag_program on Mac | FTDI -3 |
| 2026-03-31 | openFPGALoader --cable xpc | FTDI -3 |
| 2026-04-01 | fxload install | Requires Xcode |
| 2026-04-01 | USB check | DLC10 stuck in PID 0x0013 |
| 2026-04-01 | fxload without sudo | 7962 bytes, PID stuck 0x0013 |
| 2026-04-01 | fxload with sudo | 7962 bytes, PID stuck 0x0013 |
| 2026-04-01 | openFPGALoader -c digilent | FTDI -3 |
| 2026-04-01 | cable reconnect | PID stays 0x0013 |
| **2026-04-01** | **fxload + replug + fxload** | **PID → 0x0008 ✅** |
| **2026-04-01** | **xc3sprog -c xpc detect** | **XC7A100T found ✅** |
| **2026-04-01** | **xc3sprog flash led_fixed.bit** | **30.6M bits in 23.3s ✅** |
