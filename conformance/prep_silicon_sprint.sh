#!/bin/bash
# prep_silicon_sprint.sh — Build bitstream list for Silicon Sprint.
# Outputs a list of (format, op) pairs that need bitstreams for HW verification.
# Run BEFORE hw_silicon_sprint.sh to know what bitstreams are needed.
cd "$(cd "$(dirname "$0")/.." && pwd)"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  SILICON SPRINT PREP — Bitstream Requirements               ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# Phase 1: Decode bitstreams (77 formats) — already in /tmp/bitstreams/
echo "=== PHASE 1: DECODE (77 bitstreams needed) ==="
echo "Check: ls /tmp/bitstreams/*.bit | wc -l"
ls /tmp/bitstreams/*.bit 2>/dev/null | wc -l
echo "If <80, need to rebuild via CI or synth"

echo ""
echo "=== PHASE 2: COMPUTE (5 formats × 5 ops = 25 bitstreams needed) ==="
COMPUTE_FMTS="gf4 gf8 gf16 gf32 bf16"
COMPUTE_OPS="add mul div sqrt quire"
NEEDED=0; PRESENT=0
for fmt in $COMPUTE_FMTS; do
    for op in $COMPUTE_OPS; do
        bitfile="/tmp/bitstreams/${fmt}_${op}.bit"
        NEEDED=$((NEEDED + 1))
        if [ -f "$bitfile" ]; then
            echo "  OK   ${fmt}_${op}.bit"
            PRESENT=$((PRESENT + 1))
        else
            echo "  MISS ${fmt}_${op}.bit — need CI build"
        fi
    done
done
echo ""
echo "Compute bitstreams: $PRESENT/$NEEDED present"

echo ""
echo "=== NEXT STEPS ==="
echo "1. Build missing bitstreams via CI (push to trigger workflows)"
echo "2. Copy CI artifacts to /tmp/bitstreams/"
echo "3. Run: sudo bash conformance/hw_silicon_sprint.sh"
