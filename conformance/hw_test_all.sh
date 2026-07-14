#!/bin/bash
# hw_test_all.sh — Full 77-format HW test on AX7203
# Runs entirely as root, writes results to the repo directory.
# Usage: sudo bash conformance/hw_test_all.sh
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

PORT="/dev/cu.usbserial-1120"
CFG="fpga/openxc7-synth/ax7203_al321.cfg"
HOST="conformance/corona_decode_host_ax7203.py"
OUT="$REPO_DIR/HW_RESULTS.txt"
PASS=0; FAIL=0; SMOKE=0; TOTAL=0

declare -a FORMATS=(
  "binary16|host|12" "binary32|dedicated|binary32" "binary64|dedicated|binary64"
  "binary128|dedicated|binary128" "binary256|dedicated|binary256" "bf16|host|0"
  "tf32|host|11" "x87_fp80|dedicated|x87_fp80"
  "decimal32|dedicated|decimal32" "decimal64|dedicated|decimal64" "decimal128|dedicated|decimal128"
  "posit8|host|4" "posit16|dedicated|posit16" "posit32|dedicated|posit32" "posit64|dedicated|posit64"
  "takum8|dedicated|takum8" "takum16|dedicated|takum16" "takum32|dedicated|takum32" "takum64|dedicated|takum64"
  "lns8|host|10" "lns16|dedicated|lns16" "lns32|dedicated|lns32" "lns64|dedicated|lns64"
  "int4|host|7" "int8|host|2" "int16|dedicated|int16" "int32|dedicated|int32" "int64|dedicated|int64" "int128|dedicated|int128"
  "minifloat|dedicated|minifloat" "fp4|host|6" "fp6_e2m3|host|8" "fp6_e3m2|host|9" "fp8_e5m2|host|5" "e8m0|dedicated|e8m0"
  "mxfp4|dedicated|mxfp4" "mxfp4_block|mxfp4blk|" "mxfp6|dedicated|mxfp6" "mxfp8_e4m3|dedicated|mxfp8_e4m3"
  "mxint8|dedicated|mxint8" "mxgf4|dedicated|mxgf4" "mxgf6|dedicated|mxgf6"
  "gf4|gf_wide|" "gf6|gf_wide|" "gf8|gf_wide|" "gf10|dedicated|gf10" "gf12|gf_wide|"
  "gf14|dedicated|gf14" "gf16|dedicated|gf16" "gf20|gf_wide|" "gf24|dedicated|gf24" "gf32|dedicated|gf32"
  "gf48|dedicated|gf48" "gf64|dedicated|gf64" "gf96|dedicated|gf96" "gf128|dedicated|gf128" "gf256|dedicated|gf256"
  "gf8_bfp|dedicated|gf8_bfp" "gf_lns_hybrid|dedicated|gf_lns_hybrid" "gfternary|dedicated|gfternary"
  "vax_f|dedicated|vax_f" "vax_d|dedicated|vax_d" "vax_g|dedicated|vax_g" "vax_h|dedicated|vax_h"
  "cray_float|dedicated|cray_float" "ms_mbf32|dedicated|ms_mbf32" "ms_mbf64|dedicated|ms_mbf64"
  "ibm_hfp32|dedicated|ibm_hfp32" "ibm_hfp64|dedicated|ibm_hfp64" "ibm_hfp128|dedicated|ibm_hfp128"
  "bcd|dedicated|bcd" "afp|dedicated|afp"
  "double_double|dedicated|double_double" "quad_double|dedicated|quad_double" "q-format|dedicated|q_format"
  "nf4|host|3" "bitnet|dedicated|bitnet"
)

echo "TRINITY HW TEST — $(date)" > "$OUT"

for entry in "${FORMATS[@]}"; do
  IFS='|' read -r bit ttype arg <<< "$entry"
  TOTAL=$((TOTAL + 1))
  bitfile="/tmp/bitstreams/${bit}.bit"

  if [ ! -f "$bitfile" ]; then
    echo "[$TOTAL] $bit: SKIP (no bitstream)" >> "$OUT"
    FAIL=$((FAIL + 1)); continue
  fi

  printf "[%d/77] %-16s " "$TOTAL" "$bit" | tee -a "$OUT"

  kextunload -b com.apple.driver.AppleSerialShim 2>/dev/null; sleep 0.5
  openocd -f "$CFG" -c "init" -c "pld load 0 $bitfile" -c "runtest 200000" -c "shutdown" 2>/dev/null
  kextload -b com.apple.driver.AppleSerialShim 2>/dev/null; sleep 1.0

  case "$ttype" in
    dedicated) cmd="python3 conformance/${arg}_decode_conformance_ax7203.py --port $PORT" ;;
    host) cmd="python3 $HOST --port $PORT --fmt $arg" ;;
    gf_wide) cmd="python3 conformance/gf_wide_decode_conformance_ax7203.py --fmt $bit --port $PORT" ;;
    mxfp4blk) cmd="python3 conformance/mxfp4_block_host_ax7203.py --port $PORT" ;;
  esac

  OUT2=$(perl -e 'alarm 60; exec @ARGV' $cmd 2>&1)
  if echo "$OUT2" | grep -qE "fails=0|bit-exact"; then
    result=$(echo "$OUT2" | grep -oE "[0-9]+/[0-9]+" | head -1)
    echo "PASS ($result)" | tee -a "$OUT"
    PASS=$((PASS + 1))
  else
    echo "FAIL" | tee -a "$OUT"
    FAIL=$((FAIL + 1))
  fi
done

echo "" >> "$OUT"
echo "SUMMARY: PASS=$PASS FAIL=$FAIL TOTAL=$TOTAL" >> "$OUT"
echo ""
echo "=== DONE ==="
echo "PASS=$PASS FAIL=$FAIL TOTAL=$TOTAL"
echo "Results: $OUT"
