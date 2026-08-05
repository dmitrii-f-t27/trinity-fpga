#!/bin/bash
# NOTE (2026-08-05): per the no-shell-scripts rule (CLAUDE.md),
# fpga/**/*.sh is slated to migrate to `tri` subcommands / Zig.
# Do not extend this script; disposition tracked in trinity-fpga#425.
# A Zig replacement already exists: prefer `fpga-flash` (src/cli/fpga_flash.zig,
# subcommands fxload|verify-pid|flash|uart-test|full).
# Flash quantum bridge bitstream with auto-initialization

BITSTREAM="${1:-/Users/playra/trinity-w1/fpga/openxc7-synth/quantum_bridge_violation.bit}"
FXLOAD="/Users/playra/trinity-w1/fpga/tools/fxload"
FIRMWARE="/Users/playra/trinity-w1/fpga/tools/xusb_xp2.hex"
JTAG_PROG="/Users/playra/trinity-w1/fpga/tools/jtag_program"

echo "🔌 Initializing JTAG cable..."
sudo "$FXLOAD" -t fx2 -d 03fd:0013 -i "$FIRMWARE" 2>/dev/null

echo "⚡ Flashing: $BITSTREAM"
sudo "$JTAG_PROG" "$BITSTREAM"

echo "✅ Done!"
