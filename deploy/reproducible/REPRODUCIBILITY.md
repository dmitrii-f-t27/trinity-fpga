# Reproducible openXC7 Bitstream Builds

> **Trust anchor for DePIN compute attestation.**
> A reproducible bitstream is a verifiable compute primitive: any party can
> independently rebuild it and check `SHA256(bitstream)` matches the
> attestation key.

**Agents:** K (Kernel/FPGA) · F (Conformance) · D (De-Zigfication) · W (Workflow/seal)

---

## The Problem

Trinity's CI currently uses `regymm/openxc7:latest` — a floating tag. Two builds
on different days may use different yosys/nextpnr commits, producing different
bitstreams for the same Verilog source. This breaks the DePIN trust model:
if the bitstream hash is not reproducible, the attestation is unverifiable.

**The fix:** pin every tool to an exact version/commit inside a Docker image,
so `SHA256(design.bit)` is a function of `(source files, git commit)` only.

---

## What Is Reproducible

| Stage | Reproducible? | Notes |
|-------|:---:|-------|
| **Yosys synthesis** (Verilog → JSON netlist) | ✅ Yes | Deterministic given exact yosys version. `synth_xilinx` is order-stable. |
| **nextpnr place & route** (JSON → FASM) | ⚠️ Partial | nextpnr uses a stochastic router. `--seed 1` + `--router router1` improve stability but **routing may vary across hosts** (thread scheduling, RNG). |
| **fasm2frames** (FASM → frames) | ✅ Yes | Pure data transform, fully deterministic. |
| **xc7frames2bit** (frames → .bit) | ✅ Yes | Bitstream assembly is deterministic given identical frames + part.yaml. |

### nextpnr Non-Determinism — Mitigation Strategy

nextpnr's router is not guaranteed bit-identical across runs. Our approach:

1. **Pin `--seed 1` and `--router router1`** — the same algorithm, same seed.
2. **Pin the exact nextpnr commit** in the Dockerfile — same binary.
3. **Pin the chipdb** (device model) — same place/route graph.
4. **Accept divergence at the FASM level, not the bitstream level.** If two
   nodes produce different bitstreams, the attestation includes the full FASM
   so a third party can verify they route the **same logical design**.

**Practical expectation:** For small designs (≤5% utilization, like the GF16
ALU at 4267 LUT / 6.7%), nextpnr is deterministic in practice on identical
hardware. For large designs (>50% utilization), expect occasional routing
divergence. The attestation protocol handles this by recording both
`bitstream_hash` and `vectors_hash` (the logical conformance result).

---

## Build Procedure

### Prerequisites

- Docker (with `linux/amd64` emulation on Apple Silicon: `docker buildx`)
- The pinned Dockerfile at `deploy/reproducible/Dockerfile.openxc7-pinned`

### One-Command Build

```bash
# Build GF16 add design reproducibly
./deploy/reproducible/build_reproducible.sh \
    corona_compute_gf16_add_ax7203 \
    gf_adder_param.v gf_mul_param.v corona_compute_gf16_add_ax7203.v
```

This:
1. Builds the pinned Docker image (if not cached).
2. Runs the 4-step openXC7 flow inside it.
3. Computes `SHA256(bitstream)`.
4. Calls `bitstream_provenance.py` to bind source → bitstream.
5. Writes an attestation stub (`<design>.attestation.json`).

### Manual Reproduction (for third-party verification)

```bash
# 1. Build the exact image
docker build -f deploy/reproducible/Dockerfile.openxc7-pinned \
    -t trinity-openxc7-pinned .

# 2. Run the flow
docker run --rm -v "$(pwd)/fpga/openxc7-synth:/work" trinity-openxc7-pinned bash -c '
    cd /work &&
    yosys -p "read_verilog gf_adder_param.v gf_mul_param.v corona_compute_gf16_add_ax7203.v; \
              synth_xilinx -abc9 -nocarry -arch xc7; \
              write_json corona_compute_gf16_add_ax7203.json" &&
    nextpnr-xilinx --chipdb /opt/chipdb/xc7a200tfbg484-2.bin \
        --json corona_compute_gf16_add_ax7203.json \
        --xdc ax7203_corona.xdc \
        --fasm corona_compute_gf16_add_ax7203.fasm \
        --router router1 --seed 1 --freq 10.0 &&
    fasm2frames --db-root /opt/prjxray-db/artix7 --part xc7a200tfbg484-2 \
        corona_compute_gf16_add_ax7203.fasm corona_compute_gf16_add_ax7203.frames &&
    xc7frames2bit \
        --part_file /opt/prjxray-db/artix7/xc7a200tfbg484-2/part.yaml \
        --frm_file corona_compute_gf16_add_ax7203.frames \
        --output_file corona_compute_gf16_add_ax7203.bit
'

# 3. Verify the hash
shasum -a 256 fpga/openxc7-synth/corona_compute_gf16_add_ax7203.bit
```

If your hash matches the attestation's `bitstream_hash`, the bitstream is
proven to come from the claimed source + toolchain.

---

## Toolchain Pinning Audit

The Dockerfile pins these versions. The `TODO(K)` commits must be filled from
a one-time audit of the `regymm/openxc7:latest` image that CI currently uses:

```bash
# Run these inside the current CI image to extract the exact commits:
docker run --rm regymm/openxc7:latest bash -c '
    echo "yosys: $(yosys -V)"
    echo "nextpnr: $(cd /nextpnr-xilinx && git rev-parse HEAD)"
    echo "prjxray: $(cd /prjxray && git rev-parse HEAD)"
    echo "prjxray-db: $(cd /nextpnr-xilinx/xilinx/external/prjxray-db && git rev-parse HEAD)"
    echo "nextpnr-meta: $(cd /nextpnr-xilinx/xilinx/external/nextpnr-xilinx-meta && git rev-parse HEAD)"
'
```

Paste the output into the `ENV` variables at the top of `Dockerfile.openxc7-pinned`.

### Current Known Versions

| Tool | Version | Source |
|------|---------|--------|
| yosys | **0.63** | `research/goldenfloat-hw-conformance/GOLDENFLOAT_HW_CONFORMANCE_v0.2.md` |
| nextpnr-xilinx | `TODO(K)` — audit needed | `regymm/openxc7:latest` |
| prjxray | `TODO(K)` — audit needed | `regymm/openxc7:latest` |
| prjxray-db (artix7) | `TODO(K)` — audit needed | `regymm/openxc7:latest` |
| Target part | `xc7a200tfbg484-2` | AX7203 board |
| Base image | `ubuntu:22.04` | Docker Hub (pinned by digest) |

---

## Trust Model

```
┌─────────────────────────────────────────────────────────┐
│                    TRUST CHAIN                           │
│                                                         │
│  Source (Verilog)                                        │
│    │  SHA256(source files)                               │
│    ▼                                                     │
│  Pinned Toolchain (Docker image)                         │
│    │  toolchain_provenance.json (commits + versions)     │
│    ▼                                                     │
│  Bitstream (.bit)                                        │
│    │  SHA256(bitstream) = ATTESTATION KEY                │
│    ▼                                                     │
│  Conformance Proof                                       │
│    │  vectors_hash + results_hash (all_passed = true)    │
│    ▼                                                     │
│  Ed25519 Signature                                       │
│    │  node signs the full attestation                    │
│    ▼                                                     │
│  DePIN Network                                           │
│       any peer can: rebuild → verify hash → check sig    │
└─────────────────────────────────────────────────────────┘
```

### What an attacker would need to forge

To produce a valid attestation for a malicious bitstream, an attacker must:

1. **Forge the source hashes** — requires SHA256 preimage (infeasible).
2. **Match the bitstream hash** — requires reproducing the exact toolchain
   output with different Verilog (infeasible for non-trivial designs).
3. **Forge the Ed25519 signature** — requires breaking Ed25519 (infeasible).

### What is NOT claimed

- We do **not** claim the bitstream is free of hardware backdoors in the
  Xilinx silicon. The prjxray database is reverse-engineered, not vendor-
  provided. A bitstream that matches the FASM is "correct by construction"
  relative to the open-source toolchain, not relative to Xilinx's proprietary
  bitstream format.
- We do **not** claim nextpnr routing is bit-identical across all hosts.
  See "nextpnr Non-Determinism" above.

---

## CI Integration

To make CI use the pinned image instead of `regymm/openxc7:latest`, update
`.github/workflows/build-ax7203-bitstream.yml`:

```yaml
# Before:
docker run --rm -v "$(pwd):/github" regymm/openxc7:latest ...

# After:
docker run --rm -v "$(pwd):/github" trinity-openxc7-pinned ...
```

And add a pre-build step:

```yaml
- name: Build pinned toolchain image
  run: |
    docker build -f deploy/reproducible/Dockerfile.openxc7-pinned \
        -t trinity-openxc7-pinned deploy/reproducible/
```

---

## Files

| File | Purpose |
|------|---------|
| `Dockerfile.openxc7-pinned` | Pinned toolchain image (trust root) |
| `build_reproducible.sh` | Wrapper: build design + emit attestation stub |
| `REPRODUCIBILITY.md` | This document |
| `../../hardware/tools/bitstream_provenance.py` | Source↔bitstream manifest tool |
| `../../src/trinity_node/attestation.zig` | Zig module: sign/verify attestations |
| `../../deploy/contracts/ATTESTATION_PROTOCOL.md` | Wire protocol spec |

---

φ² + 1/φ² = 3 = TRINITY
