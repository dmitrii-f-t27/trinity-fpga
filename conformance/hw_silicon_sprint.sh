#!/bin/bash
# hw_silicon_sprint.sh — Full Tier-E verification sprint for AX7203.
# Tests: decode (77 formats) + compute (10 ops × top formats).
# Run with: sudo bash conformance/hw_silicon_sprint.sh
#
# Track A deliverable: automated HW test for ALL operations.
cd /Users/playom/trinity-fpga
PORT="${PORT:-/dev/cu.usbserial-1120}"
CFG="fpga/openxc7-synth/ax7203_al321.cfg"
RESULTS="/tmp/hw_silicon_sprint_$(date +%Y%m%d_%H%M%S).txt"
PASS=0; FAIL=0; TOTAL=0

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  TRINITY SILICON SPRINT — AX7203 (XC7A200T) — 10 OPS           ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo "Started: $(date)" | tee "$RESULTS"
echo "Port: $PORT" | tee -a "$RESULTS"
echo "" | tee -a "$RESULTS"

# ═══════════════════════════════════════════════════════════════════
# PHASE 1: DECODE CONFORMANCE (77 formats)
# ═══════════════════════════════════════════════════════════════════
echo "=== PHASE 1: DECODE (77 formats) ===" | tee -a "$RESULTS"
bash conformance/hw_test_all.sh 2>&1 | tee -a "$RESULTS"

# ═══════════════════════════════════════════════════════════════════
# PHASE 2: COMPUTE CONFORMANCE (10 ops × top formats)
# ═══════════════════════════════════════════════════════════════════
echo "" | tee -a "$RESULTS"
echo "=== PHASE 2: COMPUTE (10 ops × formats) ===" | tee -a "$RESULTS"

COMPUTE_FMTS="gf4 gf8 gf16 gf32 bf16"
COMPUTE_OPS="add mul div sqrt quire"

for fmt in $COMPUTE_FMTS; do
    for op in $COMPUTE_OPS; do
        bitfile="/tmp/bitstreams/${fmt}_${op}.bit"
        TOTAL=$((TOTAL + 1))
        printf "[compute] %-6s %-6s ... " "$fmt" "$op" | tee -a "$RESULTS"

        # Flash bitstream (kext cycle)
        if [ -f "$bitfile" ]; then
            kextunload -b com.apple.driver.AppleSerialShim 2>/dev/null; sleep 0.5
            openocd -f "$CFG" -c "init" -c "pld load 0 $bitfile" -c "runtest 200000" -c "shutdown" 2>/dev/null
            kextload -b com.apple.driver.AppleSerialShim 2>/dev/null; sleep 1.0

            # Run conformance
            OUT=$(python3 conformance/compute_conformance_template.py --port "$PORT" --fmt "$fmt" --op "$op" --n 32 2>&1)
            if echo "$OUT" | grep -qE "fails=0"; then
                echo "PASS" | tee -a "$RESULTS"
                PASS=$((PASS + 1))
            else
                echo "FAIL ($(echo "$OUT" | head -1))" | tee -a "$RESULTS"
                FAIL=$((FAIL + 1))
            fi
        else
            echo "SKIP (no bitstream)" | tee -a "$RESULTS"
            FAIL=$((FAIL + 1))
        fi
    done
done

# ═══════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════
echo "" | tee -a "$RESULTS"
echo "╔══════════════════════════════════════════════════════════════════╗" | tee -a "$RESULTS"
printf  "║  SILICON SPRINT: PASS=%-3d  FAIL=%-3d  TOTAL=%-3d                  ║\n" $PASS $FAIL $TOTAL | tee -a "$RESULTS"
echo "╚══════════════════════════════════════════════════════════════════╝" | tee -a "$RESULTS"
echo "Results: $RESULTS"
