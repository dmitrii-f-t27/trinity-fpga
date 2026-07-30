# gf512 — strict SW-bitexact (horizon-A, Trinity Catalog-100)

**Date:** 2026-07-30. **Author:** Vasilev (gHashTag), ORCID 0009-0008-4294-6159.

## What was closed
gf512 = GF(N=512, E=195, M=316, BIAS=2^194−1) promoted to **strict SW-bitexact**,
3 witnesses. M=316 → **264 mantissa bits rounded RNE** per normal decode (the
widest rounded path before gf1024). Continuation of gf48/gf96/gf128/gf256.

**Theoretical-only format:** GF512 ≈ 401% of XC7A200T
(`research/COMPLETE_LUT_TABLE.md`) — the decode law is provably bit-exact (3
witnesses) but it can **never be Tier-E** (does not fit any current FPGA).

## Three independent witnesses (`[proven]`)
| # | Witness | Implementation |
|---|---------|----------------|
| A | `witness_A` | exact mpmath mpf (dps=400 ≫ 316 bits) → frexp+scaling+RNE half-cmp |
| B | `witness_B` | pure integer field-construct, guard/sticky for 316→52, ±2^194 exponent as int |
| C | `gf512_decode_fp64.v` | fixed-width Verilog, BIAS as 194-bit all-ones localparam, E2 signed [200:0], 317-bit full_sig, iverilog 13.0 |

```
WITNESS CROSS-CHECK (A mpmath-exact vs B integer-construct): 32480/32480 agree (mismatch=0)
HW RESULT: 32480/32480 bit-exact (fails=0)     # RTL (C) vs oracle
```
Passed on the first RTL run (the gf96 signed-sum lesson + the BIAS off-by-one
were both applied before run).

## Tier and bounds (BINDING)
- **Strict SW-bitexact** `[proven]` — **NOT Tier-E and never can be** (GF512 >
  4× the largest target FPGA). No synth/PnR/flash is possible.
- Horizon-A: SW-bitexact 73→74, remaining selfconsistent 2→1 (only `gf1024`).

## Files
- `conformance/gf512_bitexact_oracle.py` — witnesses A + B
- `conformance/gf512_vectors.hex` — 32480 vectors "<512-bit raw> <64-bit expected>"
- `fpga/openxc7-synth/gf512_decode_fp64.v` — RTL witness C
- `fpga/openxc7-synth/tb_gf512_decode_fp64.v` — iverilog testbench

## Reproduce
```bash
cd conformance && python3 gf512_bitexact_oracle.py
cp gf512_vectors.hex /tmp/ && cd /tmp
iverilog -g2012 -o gf512_tb ../<repo>/fpga/openxc7-synth/gf512_decode_fp64.v \
                            ../<repo>/fpga/openxc7-synth/tb_gf512_decode_fp64.v
vvp gf512_tb
```
