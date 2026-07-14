# Trinity DePIN Attestation Protocol

> **Protocol version:** 1.0
> **Status:** Draft
> **Agents:** K (Kernel/FPGA) · F (Conformance) · V (Verdict) · Y (Yield/DePIN)

A reproducible openXC7 bitstream is a **verifiable compute primitive**. This
protocol defines how a DePIN node proves it ran a specific FPGA design, and how
any third party can independently verify that claim.

The trust root is **bitstream reproducibility**: if any party can rebuild the
exact `.bit` file from pinned source + toolchain and get the same SHA256, the
bitstream is a cryptographic commitment to the design.

---

## Protocol Overview

```
┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
│  1. BUILD│─────▶│ 2. ATTEST│─────▶│  3. PROVE│─────▶│ 4. VERIFY│
│  openXC7 │      │  SHA256  │      │  Conform.│      │  Rebuild │
│  → .bit  │      │  → key   │      │  → proof │      │  → check │
└──────────┘      └──────────┘      └──────────┘      └──────────┘
```

### Phase 1 — BUILD

The node (or a designated builder) synthesizes a Verilog design through the
pinned openXC7 toolchain:

```
Verilog source → yosys → nextpnr-xilinx → fasm2frames → xc7frames2bit → bitstream.bit
```

All tools are pinned in `deploy/reproducible/Dockerfile.openxc7-pinned`. The
output is:

- `bitstream.bit` — the FPGA configuration image
- `bitstream.bit.provenance.json` — source hashes + tool versions + git commit

### Phase 2 — ATTEST

The **attestation key** is:

```
SHA256(bitstream.bit)
```

This hash is the cryptographic commitment to `(source, toolchain, routing)`.
It is included in every attestation message.

### Phase 3 — PROVE

The node loads `bitstream.bit` onto its FPGA and runs a **conformance vector**
through it. The vector is a set of known input→output pairs from the Trinity
conformance suite (e.g. `t27/conformance/gf16_vectors.json`).

The node records:

- `vectors_hash` — SHA256 of the conformance vector file used
- `results_hash` — SHA256 of all FPGA outputs, concatenated
- `all_passed` — whether every output matched the expected value

It then signs the full attestation with its Ed25519 private key.

### Phase 4 — VERIFY

Any party (a DePIN peer, a light client, a smart contract oracle) can verify
the claim **without trusting the node**:

1. **Rebuild**: Download the source at the claimed git commit, rebuild the
   bitstream using the pinned Docker image.
2. **Check hash**: `SHA256(rebuilt.bit) == attestation.bitstream_hash`?
3. **Check conformance**: Re-run the conformance vector in simulation or on
   their own FPGA. Does `results_hash` match?
4. **Check signature**: `Ed25519.verify(attestation, node_public_key)`?

If all four pass, the attestation is valid. The node genuinely ran the claimed
FPGA design and produced the claimed results.

---

## Protocol Messages

### 1. Full Attestation (signed)

```json
{
  "protocol": "trinity-depin-attestation/v1",
  "attestation": {
    "bitstream_hash": "sha256:a1b2c3d4e5f6...64hexchars",
    "source_commit": "git:abc123def456",
    "source_dirty": false,
    "design": "corona_compute_gf16_add_ax7203",
    "target_part": "xc7a200tfbg484-2",
    "docker_image": "trinity-openxc7-pinned",
    "docker_image_id": "sha256:e5f6a7b8...",
    "toolchain_provenance": {
      "yosys_version": "0.63",
      "nextpnr_commit": "1a2b3c4d...",
      "prjxray_commit": "5e6f7a8b...",
      "prjxray_db_commit": "9c0d1e2f...",
      "fasm_version": "0.0.2.post0"
    },
    "conformance_proof": {
      "format": "gf16",
      "operation": "add",
      "vectors_hash": "sha256:f1e2d3c4...",
      "results_hash": "sha256:b5a69788...",
      "vector_count": 42,
      "all_passed": true
    },
    "timestamp": "2026-07-14T12:00:00Z",
    "node_public_key": "ed25519:9a8b7c6d...64hexchars"
  },
  "node_signature": "ed25519:1234abcd...128hexchars"
}
```

### 2. Challenge Request (from verifier to node)

A verifier that wants proof the node is actually running the FPGA (not
emulating) sends a challenge:

```json
{
  "protocol": "trinity-depin-attestation/v1",
  "type": "challenge",
  "challenge_id": "uuid-...",
  "bitstream_hash": "sha256:a1b2c3d4...",
  "input_vector": [0, 1, 2, 3, 255, 65535],
  "input_format": "gf16",
  "operation": "add",
  "nonce": "random-32-bytes-hex",
  "deadline_ms": 5000
}
```

### 3. Challenge Response (from node)

The node must compute the result **on the FPGA** and respond within the
deadline. The latency proves it used hardware (software emulation would be
too slow or too fast):

```json
{
  "protocol": "trinity-depin-attestation/v1",
  "type": "challenge_response",
  "challenge_id": "uuid-...",
  "output_vector": [1, 3, 5, 258, 65535],
  "output_format": "gf16",
  "fpga_latency_ns": 340,
  "nonce": "random-32-bytes-hex",
  "node_signature": "ed25519:..."
}
```

**Why latency matters:** A real FPGA produces a GF16 add in <500 ns. A
software emulator (even optimized) takes 1–10 µs. A malicious node claiming
FPGA execution but actually emulating cannot match the latency distribution.
Repeated challenges build a statistical fingerprint of genuine hardware.

---

## Signature Scope

The Ed25519 signature covers the **canonical JSON serialization** of the
`attestation` object (everything inside the outer `attestation` key, excluding
`node_signature`).

Canonicalization rules:

1. Keys sorted alphabetically (RFC 8785 JCS).
2. No insignificant whitespace.
3. UTF-8 encoded.
4. `node_public_key` is included in the signed payload (binds signature to key).

```
message_to_sign = canonical_json(attestation_object)
signature = ed25519_sign(message_to_sign, node_private_key)
```

---

## Conformance Vector Format

Conformance vectors come from `t27/conformance/<format>_vectors.json`. Each
vector file contains:

```json
{
  "format_name": "GF16",
  "format_bits": 16,
  "test_vectors": [
    { "input": { "a": "0x0000", "b": "0x0001" },
      "expected": { "result": "0x0001" } },
    ...
  ]
}
```

The attestation references:

- `vectors_hash` = `SHA256(canonical_json(vector_file))`
- `results_hash` = `SHA256(concat(all_fpga_outputs_in_order))`

A verifier re-runs the same vectors and checks both hashes match.

---

## Supported Operations

| Operation | Conformance File | FPGA Design | Status |
|-----------|-----------------|-------------|--------|
| `gf16_add` | `gf16_vectors.json` | `corona_compute_gf16_add_ax7203` | ✅ |
| `gf16_mul` | `gf16_vectors.json` | `corona_compute_gf16_mul_ax7203` | ✅ |
| `gf8_add` | `gf8_vectors.json` | `corona_compute_gf8_*_ax7203` | ✅ |
| `gf12_mul` | `gf12_vectors.json` | `corona_compute_gf12_mul_ax7203` | ✅ |
| `fp8_e5m2_alu` | — | `corona_compute_fp8_e5m2_alu_ax7203` | 🔧 |

---

## On-Chain Integration (Future)

The attestation can be submitted to a smart contract for reward distribution:

```solidity
struct Attestation {
    bytes32 bitstreamHash;
    bytes12 sourceCommit;
    bytes32 vectorsHash;
    bytes32 resultsHash;
    bool allPassed;
    bytes32 nodePublicKey;  // Ed25519 public key (first 32 bytes)
    bytes signature;        // Ed25519 signature (64 bytes)
}
```

The contract verifies the Ed25519 signature on-chain (via a precompile or
optimistic fraud-proof scheme) and releases $TRI rewards to the node.

---

## Threat Model

| Threat | Mitigation |
|--------|-----------|
| Node fabricates results without FPGA | Challenge protocol (latency fingerprint) + conformance re-check |
| Node uses different (malicious) bitstream | `bitstream_hash` mismatch on independent rebuild |
| Node uses wrong source version | `source_commit` + source hash in provenance manifest |
| Node reports false toolchain | `toolchain_provenance` + Docker image digest |
| Stolen private key | Node key rotation + slashing for invalid attestations |
| Replay of old attestation | `timestamp` + `nonce` in challenges |

---

## Reference Implementation

| Component | File |
|-----------|------|
| Pinned toolchain | `deploy/reproducible/Dockerfile.openxc7-pinned` |
| Build wrapper | `deploy/reproducible/build_reproducible.sh` |
| Provenance tool | `hardware/tools/bitstream_provenance.py` |
| Zig attestation module | `src/trinity_node/attestation.zig` |
| Crypto (Ed25519, SHA256) | `src/trinity_node/crypto.zig` |

### Zig API (see `attestation.zig`)

```zig
const attestation = @import("attestation.zig");

// Compute the attestation key
const hash = attestation.computeBitstreamHash("design.bit");

// Verify a provenance manifest
const ok = attestation.verifyProvenance(allocator, "design.bit");

// Create + sign an attestation
var signed = attestation.createAttestation(allocator, "design.bit", "gf16", "add", results_hash, &keypair);

// Verify a signed attestation
const valid = attestation.verifyAttestation(signed, node_public_key);
```

---

φ² + 1/φ² = 3 = TRINITY
