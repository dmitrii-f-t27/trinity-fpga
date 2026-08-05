#!/bin/bash
# Flash quantum bridge bitstream with auto-initialization

# Resolve tool paths relative to this script (was hardcoded to
# /Users/playra/trinity-w1). Override the bitstream via $1 or FPGA_DIR.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FPGA_DIR="${FPGA_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
BITSTREAM="${1:-$FPGA_DIR/openxc7-synth/quantum_bridge_violation.bit}"
FXLOAD="$SCRIPT_DIR/fxload"
FIRMWARE="$SCRIPT_DIR/xusb_xp2.hex"
JTAG_PROG="$SCRIPT_DIR/jtag_program"

echo "🔌 Initializing JTAG cable..."
sudo "$FXLOAD" -t fx2 -d 03fd:0013 -i "$FIRMWARE" 2>/dev/null

echo "⚡ Flashing: $BITSTREAM"
sudo "$JTAG_PROG" "$BITSTREAM"

echo "✅ Done!"
