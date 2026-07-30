# gf1024 — strict SW-bitexact (horizon-A closure, Trinity Catalog-100)

**Date:** 2026-07-30. **Author:** Vasilev (gHashTag), ORCID 0009-0008-4294-6159.

## What was closed
gf1024 = GF(N=1024, E=391, M=632, BIAS=2^390−1) promoted to **strict SW-bitexact**,
3 witnesses. The **final format of the horizon-A line** (gf48→gf1024 all proven).
M=632 → **580 mantissa bits rounded RNE** per normal decode — the widest rounded
path in the family. BIAS = 2^390−1 (390-bit all-ones localparam).

**Theoretical-only format:** GF1024 ≈ 1605% of XC7A200T
(`research/COMPLETE_LUT_TABLE.md`) — decode is provably bit-exact (3 witnesses)
but it can **never be Tier-E** (~16× too big for any current FPGA).

## Three independent witnesses (`[proven]`)
| # | Witness | Implementation |
|---|---------|----------------|
| A | `witness_A` | exact mpmath mpf (dps=700 ≫ 632 bits) → frexp+scaling+RNE half-cmp |
| B | `witness_B` | pure integer field-construct, guard/sticky for 632→52, ±2^390 exponent as int |
| C | `gf1024_decode_fp64.v` | fixed-width Verilog, BIAS 390-bit all-ones, E2 signed [400:0], 633-bit full_sig, iverilog 13.0 |

```
WITNESS CROSS-CHECK (A mpmath-exact vs B integer-construct): 32480/32480 agree (mismatch=0)
HW RESULT: 32480/32480 bit-exact (fails=0)     # RTL (C) vs oracle
```
Passed on the first RTL run.

## Tier and bounds (BINDING)
- **Strict SW-bitexact** `[proven]` — **NOT Tier-E and never can be** (GF1024 ≈
  16× the largest target FPGA).
- **Horizon-A CLOSED**: all wide GoldenFloat formats (gf48/96/128/256/512/1024)
  are now strict SW-bitexact. Remaining catalog `selfconsistent` packs = 0 on
  this axis; the only un-promoted formats are structural-by-design (no S:E:M
  decode law) or await a 2nd-witness oracle for ADD/MUL (separate axis).

## Horizon-A summary (this session, commits c3ab8264 → this)
| Format | M | bits-rounded | vectors | RTL-first-run? |
|--------|---|-------------|---------|----------------|
| gf48   | 29  | 0   | 9616  | (prior) |
| gf96   | 59  | 7   | 59050 | no (1 bugfix — signed exp-field sum) |
| gf128  | 78  | 26  | 54640 | yes |
| gf256  | 158 | 106 | 50230 | yes |
| gf512  | 316 | 264 | 32480 | yes |
| gf1024 | 632 | 580 | 32480 | yes |

Lesson propagated: the gf96 width/sign-slicing bug (signed sum FIRST, then field
slice) was applied from gf128 onward → every subsequent RTL passed first try.

## Files
- `conformance/gf1024_bitexact_oracle.py` — witnesses A + B
- `conformance/gf1024_vectors.hex` — 32480 vectors "<1024-bit raw> <64-bit expected>"
- `fpga/openxc7-synth/gf1024_decode_fp64.v` — RTL witness C
- `fpga/openxc7-synth/tb_gf1024_decode_fp64.v` — iverilog testbench

## Reproduce
```bash
cd conformance && python3 gf1024_bitexact_oracle.py
cp gf1024_vectors.hex /tmp/ && cd /tmp
iverilog -g2012 -o gf1024_tb ../<repo>/fpga/openxc7-synth/gf1024_decode_fp64.v \
                             ../<repo>/fpga/openxc7-synth/tb_gf1024_decode_fp64.v
vvp gf1024_tb
```
