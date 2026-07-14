# FTDI No-Serial Kext — macOS MPSSE Fix

## Problem
macOS `AppleSerialShim` claims the FTDI FT232H device (VID:0x0403, PID:0x6014),
blocking `openocd` from MPSSE bulk transfers. This prevents FPGA bitstream upload
via JTAG (`pld load`). Short scans work, but large transfers hang with
`LIBUSB_ERROR_INTERRUPTED`.

## Solution: Codeless Kext
This codeless kext matches the FTDI device with `IOProbeScore=90000` (higher than
AppleSerialShim's ~1000), preventing the serial driver from claiming it.

## Installation

```bash
# 1. Copy kext to /Library/Extensions
sudo cp -R hardware/drivers/FTDINoSerial.kext /Library/Extensions/

# 2. Set permissions
sudo chown -R root:wheel /Library/Extensions/FTDINoSerial.kext
sudo chmod -R 755 /Library/Extensions/FTDINoSerial.kext

# 3. Enable (may require reboot on Apple Silicon)
sudo kextload /Library/Extensions/FTDINoSerial.kext

# 4. Verify — replug USB cable, then check
system_profiler SPUSBDataType | grep -A5 "FTDI"
ioreg -l | grep FTDINoSerial

# 5. Test openocd
sudo openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
  -c "adapter speed 100; init; scan_chain; shutdown"
```

## After installation
- `/dev/cu.usbserial-1120` will NOT appear (serial driver blocked)
- `openocd` will have exclusive USB access → `pld load` works
- For UART conformance: temporarily `kextunload` FTDINoSerial, or use a second USB-UART

## Alternative: Temporary Fix
```bash
# This MIGHT work after replug (brief window before kext attaches):
# 1. Unplug USB cable
# 2. Replug
# 3. Immediately run openocd (within 2 seconds)
```
