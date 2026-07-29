# gf48 — strict SW-bitexact (horizon-A, Trinity Catalog-100)

**Date:** 2026-07-23. **Author:** Vasilev (gHashTag), ORCID 0009-0008-4294-6159.

## What was closed

gf48 = GF(N=48, E=18, M=29, BIAS=131071) promoted from
`bitexact_selfconsistent` (the existing FP32-truncating conformance
`gf48_decode_conformance_ax7203.py` — a single decode law, losing 6 mantissa bits
M=29→23, NO 2nd witness) to **strict SW-bitexact**: independent decoder,
abs_error == 0, THREE independent witnesses.

## Why binary64, not binary32

gf48 has M=29 mantissa bits. FP32 stores only 23 → any gf48→FP32 conversion
TRUNCATES 6 bits, so it can only ever be self-consistent, never strictly bit-exact
against an exact oracle. binary64 stores 52 bits ≥ 29 → every finite *normal* gf48
value is represented in binary64 with ZERO rounding, which makes an abs_error==0
comparison valid.

## Three independent witnesses (`[proven]`)

| # | Witness | Implementation | Role |
|---|---------|----------------|------|
| A | `witness_A` in `gf48_bitexact_oracle.py` | exact `fractions.Fraction` → correctly-rounded binary64 (RNE in arbitrary precision, `_floor_log2_frac` via bit_length, no float until the final step) | reference oracle |
| B | `witness_B` in the same file | field-by-field integer construction (NO Fraction, mirrors the RTL datapath) | 2nd independent SW-witness |
| C | `gf48_decode_fp64.v` + `tb_gf48_decode_fp64.v` via **iverilog 12.0** | fixed-width Verilog integer datapath | RTL-witness (catches truncation/OOB bugs, inv. #6) |

## Run result (2026-07-23, sandbox, iverilog 12.0)

```
WITNESS CROSS-CHECK (A exact-Fraction vs B integer-construct): 9616/9616 agree (mismatch=0)
HW RESULT: 9616/9616 bit-exact (fails=0)     # RTL (C) vs oracle
```

All three witnesses agree **9616/9616 bit-for-bit, 0 mismatches**.

## Tier and bounds (BINDING)

- This is **strict SW-bitexact** `[proven]` — NOT Tier-E (no run on AX7203
  silicon). Synth/PnR/flash on the board = `[REQUIRES USER ACTION]`, a separate
  epic (64-bit output, not the FP32 lineup).
- Sweep = representative + boundary (the fp64 normal/subnormal boundary e≈BIAS−1022)
  + a logarithmic spread across the whole exponent range + a deterministic random
  fill (seed=20260723). A full exhaustive sweep (2^48 codes) is impossible — this
  is the same strictness tier as the FPGA conformance for wide formats.
- Oracle A uses `_floor_log2_frac` via `bit_length` — WITHOUT iterative
  multiplication (otherwise the huge-power Fraction 2^(e−131071) explodes into
  million-bit integers; lesson of this session).

## Files

- `conformance/gf48_bitexact_oracle.py` — witnesses A + B, vector generation
- `conformance/gf48_vectors.hex` — 9616 vectors "<48-bit raw> <64-bit expected>"
- `fpga/openxc7-synth/gf48_decode_fp64.v` — RTL witness C
- `fpga/openxc7-synth/tb_gf48_decode_fp64.v` — iverilog testbench

## Reproduce

```bash
cd conformance && python3 gf48_bitexact_oracle.py    # A==B + writes vectors
cp gf48_vectors.hex /tmp/ && cd /tmp
iverilog -g2012 -o gf48_tb ../<repo>/fpga/openxc7-synth/gf48_decode_fp64.v \
                           ../<repo>/fpga/openxc7-synth/tb_gf48_decode_fp64.v
vvp gf48_tb                                            # C vs oracle
```
