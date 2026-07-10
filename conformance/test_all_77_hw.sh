#!/bin/bash
# test_all_77_hw.sh — Flash + conformance test ALL 77 formats on AX7203
# Run with: sudo bash conformance/test_all_77_hw.sh
#
# IMPORTANT: Must be run as root. Handles kextunload/kextload cycle
# (AppleSerialShim blocks FTDI MPSSE for large JTAG transfers).
cd /Users/playom/trinity-fpga

PORT="${PORT:-/dev/cu.usbserial-1120}"
CFG="fpga/openxc7-synth/ax7203_al321.cfg"
HOST="conformance/corona_decode_host_ax7203.py"
PASS=0; FAIL=0; SMOKE=0; TOTAL=0

# Entries: "bitstream|test_type|arg"
#   test_type=dedicated → conformance/{arg}_decode_conformance_ax7203.py
#   test_type=host       → corona_decode_host_ax7203.py --fmt {arg}
#   test_type=gf_wide    → gf_wide_decode_conformance_ax7203.py --fmt {bitstream}
#   test_type=mxfp4blk   → mxfp4_block_host_ax7203.py
#   test_type=smoke      → flash only, no conformance
declare -a FORMATS=(
  # === Standard Float (8) ===
  "binary16|host|12"
  "binary32|dedicated|binary32"
  "binary64|dedicated|binary64"
  "binary128|dedicated|binary128"
  "binary256|dedicated|binary256"
  "bf16|host|0"
  "tf32|host|11"
  "x87_fp80|dedicated|x87_fp80"
  # === Decimal (3) ===
  "decimal32|dedicated|decimal32"
  "decimal64|dedicated|decimal64"
  "decimal128|dedicated|decimal128"
  # === Posit (4) ===
  "posit8|host|4"
  "posit16|dedicated|posit16"
  "posit32|dedicated|posit32"
  "posit64|dedicated|posit64"
  # === Takum (4) ===
  "takum8|dedicated|takum8"
  "takum16|dedicated|takum16"
  "takum32|dedicated|takum32"
  "takum64|dedicated|takum64"
  # === LNS (4) ===
  "lns8|host|10"
  "lns16|dedicated|lns16"
  "lns32|dedicated|lns32"
  "lns64|dedicated|lns64"
  # === Integer (6) ===
  "int4|host|7"
  "int8|host|2"
  "int16|dedicated|int16"
  "int32|dedicated|int32"
  "int64|dedicated|int64"
  "int128|dedicated|int128"
  # === Minifloat (6) ===
  "minifloat|dedicated|minifloat"
  "fp4|host|6"
  "fp6_e2m3|host|8"
  "fp6_e3m2|host|9"
  "fp8_e5m2|host|5"
  "e8m0|dedicated|e8m0"
  # === MX Block (7) ===
  "mxfp4|dedicated|mxfp4"
  "mxfp4_block|mxfp4blk|"
  "mxfp6|dedicated|mxfp6"
  "mxfp8_e4m3|dedicated|mxfp8_e4m3"
  "mxint8|dedicated|mxint8"
  "mxgf4|dedicated|mxgf4"
  "mxgf6|dedicated|mxgf6"
  # === Galois Field (18) ===
  "gf4|gf_wide|"
  "gf6|gf_wide|"
  "gf8|gf_wide|"
  "gf10|dedicated|gf10"
  "gf12|gf_wide|"
  "gf14|dedicated|gf14"
  "gf16|dedicated|gf16"
  "gf20|gf_wide|"
  "gf24|dedicated|gf24"
  "gf32|dedicated|gf32"
  "gf48|dedicated|gf48"
  "gf64|dedicated|gf64"
  "gf96|dedicated|gf96"
  "gf128|dedicated|gf128"
  "gf256|dedicated|gf256"
  "gf8_bfp|dedicated|gf8_bfp"
  "gf_lns_hybrid|dedicated|gf_lns_hybrid"
  "gfternary|dedicated|gfternary"
  # === Legacy/Vendor (7) ===
  "vax_f|dedicated|vax_f"
  "vax_d|dedicated|vax_d"
  "vax_g|dedicated|vax_g"
  "vax_h|dedicated|vax_h"
  "cray_float|dedicated|cray_float"
  "ms_mbf32|dedicated|ms_mbf32"
  "ms_mbf64|dedicated|ms_mbf64"
  # === IBM/Industry (5) ===
  "ibm_hfp32|dedicated|ibm_hfp32"
  "ibm_hfp64|dedicated|ibm_hfp64"
  "ibm_hfp128|dedicated|ibm_hfp128"
  "bcd|dedicated|bcd"
  "afp|dedicated|afp"
  # === Extended Precision (3) ===
  "double_double|dedicated|double_double"
  "quad_double|dedicated|quad_double"
  "q-format|dedicated|q_format"
  # === ML/AI (3) ===
  "nf4|host|3"
  "bitnet|dedicated|bitnet"
)

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  TRINITY ALL-77 HW CONFORMANCE TEST — AX7203 (XC7A200T)    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Port: $PORT  |  Bitstreams: /tmp/bitstreams/"
echo ""

# Verify root
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: Must run as root (sudo bash conformance/test_all_77_hw.sh)"
    exit 1
fi

RESULTS_FILE="/tmp/hw_test_77_results.txt"
echo "TRINITY ALL-77 HW TEST — $(date)" > "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

for entry in "${FORMATS[@]}"; do
  IFS='|' read -r bit ttype arg <<< "$entry"
  TOTAL=$((TOTAL + 1))
  bitfile="/tmp/bitstreams/${bit}.bit"

  if [ ! -f "$bitfile" ]; then
    echo "[$TOTAL/77] SKIP $bit — bitstream not found"
    echo "$bit: SKIP (no bitstream)" >> "$RESULTS_FILE"
    FAIL=$((FAIL + 1))
    continue
  fi

  printf "[%2d/77] %-16s ... " "$TOTAL" "$bit"

  # Unload serial shim for JTAG flash
  kextunload -b com.apple.driver.AppleSerialShim 2>/dev/null
  sleep 0.5

  # Flash bitstream
  openocd -f "$CFG" \
    -c "init" \
    -c "pld load 0 $bitfile" \
    -c "runtest 200000" \
    -c "shutdown" 2>/dev/null

  flash_rc=$?

  # Reload serial shim for UART access
  kextload -b com.apple.driver.AppleSerialShim 2>/dev/null
  sleep 1.0

  if [ $flash_rc -ne 0 ]; then
    echo "FLASH FAIL"
    echo "$bit: FLASH FAIL" >> "$RESULTS_FILE"
    FAIL=$((FAIL + 1))
    continue
  fi

  if [ "$ttype" = "smoke" ]; then
    echo "SMOKE (flash OK)"
    echo "$bit: SMOKE" >> "$RESULTS_FILE"
    SMOKE=$((SMOKE + 1))
    continue
  fi

  # Build test command
  case "$ttype" in
    dedicated)
      script="conformance/${arg}_decode_conformance_ax7203.py"
      cmd="python3 $script --port $PORT"
      ;;
    host)
      cmd="python3 $HOST --port $PORT --fmt $arg"
      ;;
    gf_wide)
      cmd="python3 conformance/gf_wide_decode_conformance_ax7203.py --fmt $bit --port $PORT"
      ;;
    mxfp4blk)
      cmd="python3 conformance/mxfp4_block_host_ax7203.py --port $PORT"
      ;;
    *)
      echo "UNKNOWN"
      FAIL=$((FAIL + 1))
      continue
      ;;
  esac

  # Run conformance test (60s timeout via perl alarm)
  OUT=$(perl -e 'alarm 60; exec @ARGV' $cmd 2>&1)
  RC=$?

  if echo "$OUT" | grep -qE "bit-exact.*fails=0|RESULT.*fails=0|fails=0"; then
    result=$(echo "$OUT" | grep -oE "[0-9]+/[0-9]+ bit-exact[^)]*" | head -1)
    [ -z "$result" ] && result="OK"
    echo "PASS ($result)"
    echo "$bit: PASS ($result)" >> "$RESULTS_FILE"
    PASS=$((PASS + 1))
  elif [ $RC -eq 124 ]; then
    echo "TIMEOUT"
    echo "$bit: TIMEOUT" >> "$RESULTS_FILE"
    FAIL=$((FAIL + 1))
  else
    short=$(echo "$OUT" | head -1)
    echo "FAIL ($short)"
    echo "$bit: FAIL ($short)" >> "$RESULTS_FILE"
    FAIL=$((FAIL + 1))
  fi
done

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
printf  "║  PASS: %-3d  FAIL: %-3d  SMOKE: %-3d  TOTAL: %-3d            ║\n" $PASS $FAIL $SMOKE $TOTAL
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Results saved to: $RESULTS_FILE"
echo ""
cat "$RESULTS_FILE"
