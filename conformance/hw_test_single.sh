#!/bin/bash
# hw_test_single.sh — Flash one bitstream + run its conformance test
# Usage: sudo bash conformance/hw_test_single.sh <bitstream_name> [test_args...]
# Example: sudo bash conformance/hw_test_single.sh bf16 --fmt 0
#          sudo bash conformance/hw_test_single.sh binary32

set -e
cd /Users/playom/trinity-fpga

PORT="/dev/cu.usbserial-1120"
CFG="fpga/openxc7-synth/ax7203_al321.cfg"
BIT="/tmp/bitstreams/${1}.bit"

if [ ! -f "$BIT" ]; then
    echo "ERROR: $BIT not found"
    exit 1
fi

echo "=== Unloading AppleSerialShim ==="
kextunload -b com.apple.driver.AppleSerialShim 2>/dev/null || true

echo "=== Flashing $BIT ==="
openocd -f "$CFG" \
    -c "init" \
    -c "pld load 0 $BIT" \
    -c "runtest 200000" \
    -c "shutdown" 2>&1

echo "=== Flash complete, waiting 2s ==="
sleep 2

# Reload the serial shim for UART access
kextload -b com.apple.driver.AppleSerialShim 2>/dev/null || true
sleep 1

echo "=== Running conformance test ==="
shift
if [ -z "$1" ]; then
    echo "No test args provided, just flashing"
    exit 0
fi

# Check if first arg starts with -- (host mode)
case "$1" in
    --fmt)
        python3 conformance/corona_decode_host_ax7203.py --port "$PORT" "$@"
        ;;
    --*)
        python3 conformance/corona_decode_host_ax7203.py --port "$PORT" "$@"
        ;;
    *)
        # Dedicated test script
        SCRIPT="conformance/${1}_decode_conformance_ax7203.py"
        if [ -f "$SCRIPT" ]; then
            python3 "$SCRIPT" --port "$PORT"
        else
            echo "Test script $SCRIPT not found"
        fi
        ;;
esac
