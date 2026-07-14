#!/bin/bash
# format_pipeline.sh — Iterative FPGA format decode-HW pipeline.
# Cron: */15 * * * * /path/to/trinity-fpga/scripts/format_pipeline.sh >> /tmp/format_pipeline.log 2>&1
#
# Each run:
# 1. Checks CI status for pending synth runs
# 2. Downloads + flashes + UART-verifies ready bitstreams
# 3. Posts Tier-E 4/4 proofs on #199
# 4. Reports progress

set -u
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR" || exit 1
LOG_PREFIX="[pipeline $(date -u +%H:%M)]"
GH="gh --repo gHashTag/trinity-fpga"
OPENOCD="/opt/homebrew/bin/openocd"
CFG="fpga/openxc7-synth/ax7203_al321.cfg"

# Formats to track (name:conformance_script)
FORMATS="gf48:gf48_decode_conformance_ax7203.py
gf64:gf64_decode_conformance_ax7203.py
gf96:gf96_decode_conformance_ax7203.py
gf128:gf128_decode_conformance_ax7203.py"

echo "$LOG_PREFIX === Format pipeline started ==="

# 1. Check CI status for each format
while IFS=: read -r fmt script; do
    # Skip if already Tier-E proven (check #199)
    if gh issue view 199 --repo gHashTag/trinity-fpga --json comments \
       --jq '.comments[].body' 2>/dev/null | grep -q "Tier-E proof.*\`${fmt}\`.*DECODE"; then
        echo "$LOG_PREFIX $fmt: already Tier-E, skip"
        continue
    fi

    # Check CI run status
    status=$($GH run list --workflow "AX7203 Corona Decode ${fmt^^}" --limit 1 \
             --json status,conclusion --jq '.[0]|"\(.status) \(.conclusion)"' 2>/dev/null)
    ci_status=$(echo "$status" | cut -d' ' -f1)
    ci_concl=$(echo "$status" | cut -d' ' -f2)

    if [ "$ci_status" = "in_progress" ] || [ "$ci_status" = "queued" ]; then
        echo "$LOG_PREFIX $fmt: CI $ci_status, waiting"
        continue
    fi

    if [ "$ci_concl" = "failure" ]; then
        echo "$LOG_PREFIX $fmt: CI FAILED (routing?), will not flash"
        continue
    fi

    if [ "$ci_concl" = "success" ]; then
        echo "$LOG_PREFIX $fmt: CI GREEN — downloading bitstream"
        RUN_ID=$($GH run list --workflow "AX7203 Corona Decode ${fmt^^}" --limit 1 \
                  --json databaseId --jq '.[0].databaseId' 2>/dev/null)
        rm -rf "/tmp/${fmt}dec"
        if ! $GH run download "$RUN_ID" -n "corona-decode-${fmt}-bitstream" -D "/tmp/${fmt}dec" 2>/dev/null; then
            echo "$LOG_PREFIX $fmt: download FAILED"
            continue
        fi
        BIT="/tmp/${fmt}dec/corona_decode_ax7203.bit"
        if [ ! -f "$BIT" ]; then
            echo "$LOG_PREFIX $fmt: bitstream not found"
            continue
        fi
        SHA=$(shasum -a 256 "$BIT" | cut -d' ' -f1)
        echo "$LOG_PREFIX $fmt: SHA=$SHA"

        # Flash
        echo "$LOG_PREFIX $fmt: flashing..."
        if ! sudo -n "$OPENOCD" -f "fpga/openxc7-synth/ax7203_al321.cfg" \
             -c "init" -c "pld load 0 $BIT" -c "runtest 200000" -c "shutdown" 2>&1 | \
             grep -q "loaded file"; then
            echo "$LOG_PREFIX $fmt: FLASH FAILED"
            continue
        fi
        # Verify IDCODE
        idcode=$(sudo -n "$OPENOCD" -f "fpga/openxc7-synth/ax7203_al321.cfg" \
                 -c "init" -c "scan_chain" -c "shutdown" 2>&1 | grep -oE "0x[0-9a-f]{8}" | head -1)
        if [ "$idcode" != "0x13636093" ]; then
            echo "$LOG_PREFIX $fmt: WRONG IDCODE $idcode (expected 0x13636093)"
            continue
        fi

        # UART verify
        echo "$LOG_PREFIX $fmt: UART verify..."
        result=$(python3 "conformance/$script" --port /dev/cu.usbserial-1120 --baud 160000 2>&1 | \
                 grep "HW RESULT")
        echo "$LOG_PREFIX $fmt: $result"

        if echo "$result" | grep -q "fails=0"; then
            echo "$LOG_PREFIX $fmt: PASS — posting Tier-E proof"
            cat > /tmp/${fmt}_proof.md << PROOF
### Tier-E proof: \`${fmt}\` DECODE (GF decode → FP32, NEW cell, 4/4 chain)

**decode-HW +1. union +1.** NEW decode cell via format_pipeline.sh cron.

- **CI run:** $RUN_ID (success, heap placer)
- **Bitstream SHA256:** \`$SHA\`
- **UART @160000:** \`$result\`
- **IDCODE:** \`0x13636093\` (XC7A200T rev 1)

Decoder = gf_decode_param (parametric, iverilog-witnessed).
PROOF
            gh issue comment 199 --repo gHashTag/trinity-fpga --body-file "/tmp/${fmt}_proof.md"
            echo "$LOG_PREFIX $fmt: proof posted ✓"
        else
            echo "$LOG_PREFIX $fmt: UART FAIL — not posting"
        fi
    fi
done <<< "$FORMATS"

echo "$LOG_PREFIX === Pipeline cycle done ==="
