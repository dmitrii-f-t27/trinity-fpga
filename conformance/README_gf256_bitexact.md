# gf256 — strict SW-bitexact (horizon-A, Trinity Catalog-100)

**Date:** 2026-07-24. **Author:** Vasilev (gHashTag), ORCID 0009-0008-4294-6159.

## What was closed

gf256 = GF(N=256, E=97, M=158, BIAS=2^96−1) promoted from
`bitexact_selfconsistent` (FP32-truncating decode conformance) to **strict
SW-bitexact**, 3 witnesses. The widest format in the gf48/gf96/gf128 line:
**M=158 → 106 mantissa bits rounded RNE** on every normal decode (gf128=26,
gf96=7, gf48=0). The canonical BIAS = 2^96−1 (`scripts/generate_all_formats.py`);
the legacy "bias Experimental" R&D flag (`GOLDENFLOAT_HW_CONFORMANCE_v0.2:82`) is
historical — this oracle uses the canonical BIAS.

## Three independent witnesses (`[proven]`)

| # | Witness | Implementation |
|---|---------|----------------|
| A | `witness_A` | exact **mpmath** mpf (dps=200 ≫ 158 bits) → `frexp`+scaling+RNE half-cmp |
| B | `witness_B` | pure **integer** field-construct, guard/sticky for 158→52, ±2^96 exponent as plain int |
| C | `gf256_decode_fp64.v` | fixed-width Verilog, BIAS 96-bit localparam, E2 signed [100:0], 159-bit full_sig, iverilog 13.0 |

```
WITNESS CROSS-CHECK (A mpmath-exact vs B integer-construct): 50230/50230 agree (mismatch=0)
HW RESULT: 50230/50230 bit-exact (fails=0)     # RTL (C) vs oracle
```

Extra cross-check: `m=2^106−1, te=0` → witness A matches `struct.pack` (0x3ff0000000000001).
Class coverage: norm 40922, sub 1052, +inf 4005, +0 2120, −0 2127, nan 4.
Boundaries `te=±1024/−1074` verified exactly. The gf96 lesson (signed-sum of the
exponent field) was applied from the start → passed on the first RTL run.

## Tier and bounds (BINDING)

- **Strict SW-bitexact** `[proven]` — NOT Tier-E (no AX7203 flash). Synth/PnR/flash
  = `[REQUIRES USER ACTION]`.
- Horizon-A: SW-bitexact 72→73, remaining selfconsistent 3→2 (`gf512/1024`).

## Files
- `conformance/gf256_bitexact_oracle.py` — witnesses A + B
- `conformance/gf256_vectors.hex` — 50230 vectors "<256-bit raw> <64-bit expected>"
- `fpga/openxc7-synth/gf256_decode_fp64.v` — RTL witness C
- `fpga/openxc7-synth/tb_gf256_decode_fp64.v` — iverilog testbench

## Reproduce
```bash
cd conformance && python3 gf256_bitexact_oracle.py
cp gf256_vectors.hex /tmp/ && cd /tmp
iverilog -g2012 -o gf256_tb ../<repo>/fpga/openxc7-synth/gf256_decode_fp64.v \
                            ../<repo>/fpga/openxc7-synth/tb_gf256_decode_fp64.v
vvp gf256_tb
```
