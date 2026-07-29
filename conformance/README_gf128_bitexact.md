# gf128 — strict SW-bitexact (horizon-A, Trinity Catalog-100)

**Date:** 2026-07-24. **Author:** Vasilev (gHashTag), ORCID 0009-0008-4294-6159.

## What was closed

gf128 = GF(N=128, E=49, M=78, BIAS=281474976710655 = 2^48−1) promoted from
`bitexact_selfconsistent` (FP32-truncating conformance, losing 55 mantissa bits
M=78→23, single decode law) to **strict SW-bitexact**: 3 independent witnesses.

Continuation of gf48/gf96 (commits `c3ab8264`, `1a7fde6c`); the widest
implementation of the technique at the time: M=78 → **26 bits rounded RNE**
(gf96 rounded 7, gf48 rounded 0).

## Three independent witnesses (`[proven]`)

| # | Witness | Implementation |
|---|---------|----------------|
| A | `witness_A` | exact **mpmath** mpf (dps=100 ≫ 78 bits) → `frexp`+scaling+RNE half-cmp |
| B | `witness_B` | pure **integer** field-construct, guard/sticky for 78→52, exponent as plain int (±2^48 never materialized) |
| C | `gf128_decode_fp64.v` | fixed-width Verilog, BIAS 48-bit localparam, E2 signed [55:0], 79-bit full_sig, iverilog 13.0 |

```
WITNESS CROSS-CHECK (A mpmath-exact vs B integer-construct): 54640/54640 agree (mismatch=0)
HW RESULT: 54640/54640 bit-exact (fails=0)     # RTL (C) vs oracle
```

Extra cross-check: `m=0x3FFFFFF, te=0` → witness A matches `struct.pack` (0x3ff0000000000001).
Class coverage: norm 45016, sub 1156, +inf 2082, −inf 2057, +0 2075, −0 2250, nan 4.
Boundaries `te=±1024/−1074` verified exactly.

## Lesson applied from the first run

The gf96 lesson (a signed exponent must not be sliced into a bit field before the
sum: `E2_post[10:0]+1023` → spurious overflow on negative E2) was applied here
from the start — `exp_field = (E2_post + 1023)` as signed, then `[10:0]`. Hence
the gf128 RTL converged 54640/54640 **without a bugfix iteration** (gf96 needed one).

## Tier and bounds (BINDING)

- **Strict SW-bitexact** `[proven]` — NOT Tier-E (no AX7203 run). Synth/PnR/flash
  = `[REQUIRES USER ACTION]` (64-bit decode candidate).
- Horizon-A: SW-bitexact 71→72, remaining selfconsistent 4→3 (`gf256/512/1024`).

## Files
- `conformance/gf128_bitexact_oracle.py` — witnesses A + B
- `conformance/gf128_vectors.hex` — 54640 vectors "<128-bit raw> <64-bit expected>"
- `fpga/openxc7-synth/gf128_decode_fp64.v` — RTL witness C
- `fpga/openxc7-synth/tb_gf128_decode_fp64.v` — iverilog testbench

## Reproduce
```bash
cd conformance && python3 gf128_bitexact_oracle.py
cp gf128_vectors.hex /tmp/ && cd /tmp
iverilog -g2012 -o gf128_tb ../<repo>/fpga/openxc7-synth/gf128_decode_fp64.v \
                            ../<repo>/fpga/openxc7-synth/tb_gf128_decode_fp64.v
vvp gf128_tb
```
