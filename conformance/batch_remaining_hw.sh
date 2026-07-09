#!/bin/bash
# batch_remaining_hw.sh — Flash and test remaining formats
# Run with: sudo bash conformance/batch_remaining_hw.sh
cd /Users/playom/trinity-fpga

PORT="/dev/cu.usbserial-1120"
CFG="fpga/openxc7-synth/ax7203_al321.cfg"
RESULTS=""

# Standard formats with dedicated conformance scripts
for fmt in posit32 posit64 vax_f vax_d vax_g vax_h x87_fp80 quad_double takum8 mxfp4 mxint8 ms_mbf32 ms_mbf64; do
    echo "=== $fmt ==="
    openocd -f "$CFG" -c "init; pld load 0 /tmp/bitstreams/${fmt}.bit; exit" 2>&1 | tail -1
    sleep 1
    OUT=$(python3 conformance/${fmt}_decode_conformance_ax7203.py --port "$PORT" 2>&1)
    echo "$OUT"
    RESULTS="$RESULTS\n$fmt: $OUT"
    sleep 0.5
done

# GF wide formats with generic conformance
for fmt in gf48 gf64 gf96 gf128; do
    echo "=== $fmt ==="
    openocd -f "$CFG" -c "init; pld load 0 /tmp/bitstreams/${fmt}.bit; exit" 2>&1 | tail -1
    sleep 1
    OUT=$(python3 conformance/gf_wide_decode_conformance_ax7203.py --fmt $fmt --port "$PORT" 2>&1)
    echo "$OUT"
    RESULTS="$RESULTS\n$fmt: $OUT"
    sleep 0.5
done

# int128
echo "=== int128 ==="
openocd -f "$CFG" -c "init; pld load 0 /tmp/bitstreams/int128.bit; exit" 2>&1 | tail -1
sleep 1
OUT=$(python3 conformance/int128_decode_conformance_ax7203.py --port "$PORT" 2>&1)
echo "$OUT"
RESULTS="$RESULTS\nint128: $OUT"

echo ""
echo "=== BATCH SUMMARY ==="
echo -e "$RESULTS"
