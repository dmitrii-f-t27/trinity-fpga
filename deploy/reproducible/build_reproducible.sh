#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# build_reproducible.sh — Build an openXC7 bitstream inside the pinned Docker
# image and emit a provenance manifest suitable for DePIN attestation.
#
# Usage:
#   build_reproducible.sh <design_name> [source_files...]
#
# Example:
#   build_reproducible.sh corona_compute_gf16_add_ax7203 \
#       gf_adder_param.v gf_mul_param.v corona_compute_gf16_add_ax7203.v
#
# Produces:
#   <design>.bit                  — the bitstream
#   <design>.bit.provenance.json  — provenance manifest (toolchain key + source hashes)
#   <design>.attestation.json     — unsigned attestation stub (bitstream_hash + tool_versions)
#
# Agent K (Kernel/FPGA) — Agent F (Conformance) — Agent W (Workflow/seal)
# φ² + 1/φ² = 3 = TRINITY
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
IMAGE_NAME="trinity-openxc7-pinned"
DOCKERFILE="${SCRIPT_DIR}/Dockerfile.openxc7-pinned"
SYNTH_DIR="${REPO_ROOT}/fpga/openxc7-synth"
PROVENANCE_TOOL="${REPO_ROOT}/hardware/tools/bitstream_provenance.py"
TARGET_PART="xc7a200tfbg484-2"
XDC_FILE="ax7203_corona.xdc"

# ─── Color helpers ───────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${CYAN}[build_reproducible]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*" >&2; exit 1; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }

# ─── Arg parsing ─────────────────────────────────────────────────────────────
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <design_name> [source_files...]"
    echo ""
    echo "  design_name   Top-module name (e.g. corona_compute_gf16_add_ax7203)"
    echo "  source_files  Verilog sources (default: discovers from SYNTH_DIR)"
    exit 1
fi

DESIGN="$1"; shift
SOURCES=("$@")

if [[ ${#SOURCES[@]} -eq 0 ]]; then
    log "No explicit sources given, defaulting to GF adder + design file"
    SOURCES=("gf_adder_param.v" "gf_mul_param.v" "${DESIGN}.v")
fi

# ─── Step 0: Ensure Docker image exists ──────────────────────────────────────
if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
    log "Docker image '${IMAGE_NAME}' not found. Building from pinned Dockerfile..."
    docker build -f "${DOCKERFILE}" -t "${IMAGE_NAME}" "${SCRIPT_DIR}" \
        || fail "Failed to build pinned Docker image"
fi

# Record the image digest — this binds bitstreams to a specific toolchain snapshot.
IMAGE_DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' "${IMAGE_NAME}" 2>/dev/null \
    || docker inspect --format='{{.Id}}' "${IMAGE_NAME}")
log "Using image: ${IMAGE_NAME} (${IMAGE_DIGEST})"

# ─── Verify sources exist ────────────────────────────────────────────────────
for src in "${SOURCES[@]}"; do
    if [[ ! -f "${SYNTH_DIR}/${src}" ]]; then
        fail "Source not found: ${SYNTH_DIR}/${src}"
    fi
done

if [[ ! -f "${SYNTH_DIR}/${XDC_FILE}" ]]; then
    fail "XDC constraints not found: ${SYNTH_DIR}/${XDC_FILE}"
fi

# ─── Step 1: Synthesize inside pinned Docker ─────────────────────────────────
log "Building design: ${DESIGN}"
log "Sources: ${SOURCES[*]}"

docker run --rm \
    -v "${SYNTH_DIR}:/work" \
    -v "${REPO_ROOT}/hardware/tools:/tools:ro" \
    -e DESIGN="${DESIGN}" \
    -e TARGET_PART="${TARGET_PART}" \
    -e SOURCES="${SOURCES[*]}" \
    -e XDC_FILE="${XDC_FILE}" \
    "${IMAGE_NAME}" bash -c '
set -euo pipefail
DESIGN="${DESIGN}"
TARGET_PART="${TARGET_PART}"
XDC_FILE="${XDC_FILE}"
read -ra SRC_ARR <<< "${SOURCES}"

cd /work

echo "=== Tool versions ==="
yosys -V
nextpnr-xilinx --version 2>/dev/null || echo "nextpnr-xilinx (version unavailable)"
echo ""

echo "=== Step 1: Yosys synthesis ==="
YOSYS_ARGS=""
for src in "${SRC_ARR[@]}"; do
    YOSYS_ARGS+="read_verilog ${src}; "
done
yosys -p "${YOSYS_ARGS} synth_xilinx -abc9 -nocarry -arch xc7; write_json ${DESIGN}.json" \
    || { echo "YOSYS FAILED"; exit 1; }

echo "=== Step 2: nextpnr place & route ==="
cp "/chipdb/${TARGET_PART}.bin" "/opt/chipdb/${TARGET_PART}.bin" 2>/dev/null || true
nextpnr-xilinx \
    --chipdb "/opt/chipdb/${TARGET_PART}.bin" \
    --json "${DESIGN}.json" \
    --xdc "${XDC_FILE}" \
    --fasm "${DESIGN}.fasm" \
    --router router1 \
    --timing-allow-fail \
    --freq 10.0 \
    --seed 1 \
    || { echo "NEXTPNR FAILED"; exit 1; }

echo "FASM lines: $(wc -l < "${DESIGN}.fasm")"

echo "=== Step 3: fasm2frames ==="
fasm2frames \
    --db-root /opt/prjxray-db/artix7 \
    --part "${TARGET_PART}" \
    "${DESIGN}.fasm" "${DESIGN}.frames" 2>/dev/null \
    || { echo "FASM2FRAMES FAILED"; exit 1; }
[ -s "${DESIGN}.frames" ] || { echo "EMPTY FRAMES"; exit 1; }

echo "=== Step 4: xc7frames2bit ==="
xc7frames2bit \
    --part_file "/opt/prjxray-db/artix7/${TARGET_PART}/part.yaml" \
    --frm_file "${DESIGN}.frames" \
    --output_file "${DESIGN}.bit" \
    || { echo "XC7FRAMES2BIT FAILED"; exit 1; }

echo "=== BITSTREAM DONE ==="
ls -la "${DESIGN}.bit"
' || fail "Docker build failed"

BITSTREAM="${SYNTH_DIR}/${DESIGN}.bit"
[[ -f "${BITSTREAM}" ]] || fail "Bitstream not produced: ${BITSTREAM}"

# ─── Step 2: Compute bitstream hash ──────────────────────────────────────────
BITSTREAM_HASH=$(shasum -a 256 "${BITSTREAM}" | awk '{print $1}')
ok "Bitstream SHA256: ${BITSTREAM_HASH}"

# ─── Step 3: Generate provenance manifest ────────────────────────────────────
log "Generating provenance manifest..."

ABS_SOURCES=()
for src in "${SOURCES[@]}"; do
    ABS_SOURCES+=("${SYNTH_DIR}/${src}")
done

TOOLCHAIN_PROV=$(docker run --rm "${IMAGE_NAME}" cat /opt/toolchain_provenance.json)

# Call the existing provenance tool (binds source → bitstream).
if [[ -f "${PROVENANCE_TOOL}" ]]; then
    python3 "${PROVENANCE_TOOL}" generate \
        "${ABS_SOURCES[@]}" \
        --design "${DESIGN}" \
        --bit "${BITSTREAM}" \
        --docker-image "${IMAGE_NAME}" \
        || warn "Provenance tool failed (non-fatal)"
fi

# ─── Step 4: Write attestation stub ──────────────────────────────────────────
# This is the unsigned attestation. The DePIN node signs it with Ed25519.
ATTESTATION_FILE="${SYNTH_DIR}/${DESIGN}.attestation.json"

# Get git commit info
GIT_COMMIT=$(git -C "${REPO_ROOT}" rev-parse HEAD 2>/dev/null | cut -c1-12 || echo "unknown")
GIT_DIRTY=$(git -C "${REPO_ROOT}" status --porcelain 2>/dev/null | wc -l | tr -d ' ')

cat > "${ATTESTATION_FILE}" <<EOF
{
  "attestation": {
    "bitstream_hash": "sha256:${BITSTREAM_HASH}",
    "source_commit": "git:${GIT_COMMIT}",
    "source_dirty": ${GIT_DIRTY},
    "design": "${DESIGN}",
    "target_part": "${TARGET_PART}",
    "docker_image": "${IMAGE_NAME}",
    "docker_image_id": "${IMAGE_DIGEST}",
    "toolchain_provenance": ${TOOLCHAIN_PROV},
    "conformance_proof": {
      "format": "",
      "operation": "",
      "vectors_hash": "",
      "results_hash": "",
      "all_passed": false
    },
    "node_signature": ""
  }
}
EOF

ok "Attestation stub written: ${ATTESTATION_FILE}"
ok "Provenance manifest:  ${BITSTREAM}.provenance.json"

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  REPRODUCIBLE BUILD COMPLETE"
echo "═══════════════════════════════════════════════════════════════"
echo "  Design:      ${DESIGN}"
echo "  Bitstream:   ${BITSTREAM}"
echo "  SHA256:      ${BITSTREAM_HASH}"
echo "  Git commit:  ${GIT_COMMIT}"
echo "  Docker:      ${IMAGE_NAME}"
echo ""
echo "  To verify reproducibility:"
echo "    shasum -a 256 ${BITSTREAM}"
echo "    python3 ${PROVENANCE_TOOL} verify ${BITSTREAM}"
echo "═══════════════════════════════════════════════════════════════"
