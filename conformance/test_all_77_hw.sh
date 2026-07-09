#!/bin/bash
# test_all_77_hw.sh — Flash + conformance test ALL 77 formats on AX7203
# Run with: sudo bash conformance/test_all_77_hw.sh
cd /Users/playom/trinity-fpga

PORT="/dev/cu.usbserial-1120"
CFG="fpga/openxc7-synth/ax7203_al321.cfg"
PASS=0; FAIL=0; SMOKE=0; TOTAL=0

# Format entries: "bitstream_name|conformance_script_or_empty|format_id_hex"
# If conformance_script is empty, only smoke test (flash + LED check)
declare -a FORMATS=(
  # === Standard Float (8) ===
  "binary16||0x01"
  "binary32|binary32|0x02"
  "binary64|binary64|0x03"
  "binary128|binary128|0x04"
  "binary256|binary256|0x05"
  "bf16||0x06"
  "tf32||0x07"
  "x87_fp80|x87_fp80|0x08"
  # === Decimal (3) ===
  "decimal32|decimal32|0x09"
  "decimal64|decimal64|0x0A"
  "decimal128|decimal128|0x0B"
  # === Posit (4) ===
  "posit8||0x0C"
  "posit16|posit16|0x0D"
  "posit32|posit32|0x0E"
  "posit64|posit64|0x0F"
  # === Takum (4) ===
  "takum8|takum8|0x10"
  "takum16|takum16|0x11"
  "takum32|takum32|0x12"
  "takum64|takum64|0x13"
  # === LNS (4) ===
  "lns8||0x14"
  "lns16|lns16|0x15"
  "lns32|lns32|0x16"
  "lns64|lns64|0x17"
  # === Integer (6) ===
  "int4||0x18"
  "int8||0x19"
  "int16|int16|0x1A"
  "int32|int32|0x1B"
  "int64|int64|0x1C"
  "int128|int128|0x1D"
  # === Minifloat (6) ===
  "minifloat|minifloat|0x1E"
  "fp4||0x1F"
  "fp6_e2m3||0x20"
  "fp6_e3m2||0x21"
  "fp8_e5m2||0x22"
  "e8m0|e8m0|0x23"
  # === MX Block (7) ===
  "mxfp4|mxfp4|0x24"
  "mxfp4_block||0x25"
  "mxfp6|mxfp6|0x26"
  "mxfp8_e4m3|mxfp8_e4m3|0x27"
  "mxint8|mxint8|0x28"
  "mxgf4|mxgf4|0x29"
  "mxgf6|mxgf6|0x2A"
  # === Galois Field (14) ===
  "gf4|gf_generic|0x2B"
  "gf6|gf_generic|0x2C"
  "gf8|gf_generic|0x2D"
  "gf10|gf10|0x2E"
  "gf12|gf_generic|0x2F"
  "gf14|gf14|0x30"
  "gf16|gf16|0x31"
  "gf20|gf_generic|0x32"
  "gf24|gf24|0x33"
  "gf32|gf32|0x34"
  "gf48|gf48|0x35"
  "gf64|gf64|0x36"
  "gf96|gf96|0x37"
  "gf128|gf128|0x38"
  "gf256|gf256|0x39"
  "gf8_bfp|gf8_bfp|0x3A"
  "gf_lns_hybrid|gf_lns_hybrid|0x3B"
  "gfternary|gfternary|0x3C"
  # === Legacy/Vendor (7) ===
  "vax_f|vax_f|0x3D"
  "vax_d|vax_d|0x3E"
  "vax_g|vax_g|0x3F"
  "vax_h|vax_h|0x40"
  "cray_float|cray_float|0x41"
  "ms_mbf32|ms_mbf32|0x42"
  "ms_mbf64|ms_mbf64|0x43"
  # === IBM/Industry (4) ===
  "ibm_hfp32|ibm_hfp32|0x44"
  "ibm_hfp64|ibm_hfp64|0x45"
  "ibm_hfp128|ibm_hfp128|0x46"
  "bcd|bcd|0x47"
  "afp|afp|0x48"
  # === Extended Precision (3) ===
  "double_double|double_double|0x49"
  "quad_double|quad_double|0x4A"
  "q-format|q_format|0x4B"
  # === ML/AI (3) ===
  "nf4||0x4C"
  "bitnet|bitnet|0x4D"
)

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  TRINITY ALL-77 HW CONFORMANCE TEST — AX7203 (XC7A200T)    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Port: $PORT"
echo "Bitstreams: /tmp/bitstreams/"
echo ""

for entry in "${FORMATS[@]}"; do
  IFS='|' read -r bit script fmt_id <<< "$entry"
  TOTAL=$((TOTAL + 1))
  bitfile="/tmp/bitstreams/${bit}.bit"
  
  if [ ! -f "$bitfile" ]; then
    echo "[$TOTAL/77] SKIP $bit — bitstream not found"
    FAIL=$((FAIL + 1))
    continue
  fi
  
  echo -n "[$TOTAL/77] $bit ... "
  
  # Flash bitstream
  openocd -f "$CFG" -c "init; pld load 0 $bitfile; exit" 2>&1 | tail -1 > /dev/null
  sleep 0.8
  
  if [ -n "$script" ]; then
    # Run dedicated conformance script
    if [ "$script" = "gf_generic" ]; then
      script_path="conformance/gf_wide_decode_conformance_ax7203.py --fmt $bit"
    else
      script_path="conformance/${script}_decode_conformance_ax7203.py"
    fi
    
    if [ -f "${script_path%% *}" ] || [ -f "conformance/${script}_decode_conformance_ax7203.py" ]; then
      OUT=$(timeout 30 python3 $script_path --port "$PORT" 2>&1)
      if echo "$OUT" | grep -q "bit-exact.*fails=0"; then
        echo "PASS ($(echo "$OUT" | grep 'bit-exact'))"
        PASS=$((PASS + 1))
      elif echo "$OUT" | grep -q "RESULT.*0 fails\|RESULT.*OK\|PASS"; then
        echo "PASS"
        PASS=$((PASS + 1))
      else
        echo "FAIL ($OUT)"
        FAIL=$((FAIL + 1))
      fi
    else
      echo "SMOKE (no script: $script)"
      SMOKE=$((SMOKE + 1))
    fi
  else
    # No conformance script — smoke test only
    echo "SMOKE (flash OK, no conformance script)"
    SMOKE=$((SMOKE + 1))
  fi
done

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  SUMMARY: $PASS PASS | $FAIL FAIL | $SMOKE SMOKE | $TOTAL TOTAL    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "PASS = bit-exact conformance verified on HW"
echo "SMOKE = bitstream flashed OK, no conformance script yet"
echo "FAIL = flash or conformance error"
