# gf96 — strict SW-bitexact (horizon-A, Trinity Catalog-100)

**Date:** 2026-07-24. **Author:** Vasilev (gHashTag), ORCID 0009-0008-4294-6159.

## What was closed

gf96 = GF(N=96, E=36, M=59, BIAS=34359738367) promoted from
`bitexact_selfconsistent` (the FP32-truncating conformance
`gf96_decode_conformance_ax7203.py` — single decode law, losing 36 mantissa bits
M=59→23, NO 2nd witness) to **strict SW-bitexact**: independent decoder,
abs_error == 0, THREE independent witnesses.

Continuation of the gf48 technique (commit `c3ab8264`) — same methodology
(binary64 + 3 witnesses + iverilog), with two qualitative differences below.

## Why binary64, and how gf96 is harder than gf48

1. **M=59 > 52.** gf96 stores 59 mantissa bits, FP32 stores 23 (36 lost), so a
   conversion to FP32 is inherently self-consistent only. binary64 stores 52 bits,
   BUT 59−52 = **7 bits still must be rounded** round-to-nearest-even. For gf48
   (M=29 ≤ 52) there was no rounding — a pure shift. Here the 59→52 RNE path is
   the substantive part of the proof, and all 3 witnesses implement it
   independently.
2. **BIAS = 34359738367 = 2^35−1 > 2^31.** The exact value `(1 + m/2^59)·2^(e−BIAS)`
   contains the power 2^(±3.4·10^10). So witness A uses **mpmath** (where the
   exponent is a separate Python int, O(1)) and NOT `fractions.Fraction` (which
   would materialize a ~10 GB integer — the same lesson as gf48's `2^(e−131071)`,
   but here infeasible at any scale). In RTL, BIAS is a 36-bit localparam (a 32-bit
   Verilog `integer` overflows) and the working exponent is signed 41-bit.
3. **Exponent range ±2^35 vs binary64 ±1023/1074.** The vast majority of gf96
   codes map to ±inf (overflow) or ±0 (underflow) in binary64; only the
   `e ≈ BIAS` window (|true_exp| ≤ ~1074) yields finite nonzero output, and only
   there can the 59→52 rounding actually bite.

## Three independent witnesses (`[proven]`)

| # | Witness | Implementation | Role |
|---|---------|----------------|------|
| A | `witness_A` in `gf96_bitexact_oracle.py` | exact **mpmath** mpf (dps=80 ≫ 59 bits → every dyadic input exact) → correctly-rounded binary64 via `frexp` + scaling to a `[2^52,2^53)` grid + RNE half-comparison (NO guard/sticky) | reference oracle |
| B | `witness_B` in the same file | field-by-field **integer** construction (NO mpmath, NO Fraction), guard/sticky bit extraction for 59→52, wide signed exponent (the huge range never materializes a big integer) | 2nd independent SW-witness |
| C | `gf96_decode_fp64.v` + `tb_gf96_decode_fp64.v` via **iverilog 13.0** | fixed-width Verilog integer datapath (BIAS as 36-bit localparam, E2 signed [40:0], 60-bit full_sig, RNE guard/sticky, overflow→±inf / underflow→±0) | RTL-witness (catches truncation/width/OOB bugs, inv. #6) |

## Run result (2026-07-24, sandbox, iverilog 13.0)

```
WITNESS CROSS-CHECK (A mpmath-exact vs B integer-construct): 59050/59050 agree (mismatch=0)
HW RESULT: 59050/59050 bit-exact (fails=0)     # RTL (C) vs oracle
```

All three witnesses agree **59050/59050 bit-for-bit, 0 mismatches**.

Extra independent cross-check: for cases where the input is exactly representable
in float64, witness A matched Python `struct.pack('>d', ...)` (e.g.
`m=0x7F, te=0` → `0x3ff0000000000001` on both sides) — a third party confirms the
RNE.

## Sweep and class coverage

59050 vectors cover all 5 decode classes and all binary64 output classes:
`norm` 49108, `sub` 1262, `+inf` 2077, `−inf` 2167, `+0` 2199, `−0` 2233, `nan` 4.

Boundaries verified exactly (true_exp = e − BIAS):
- `te = 1024 → +inf` (overflow), `te = 1023 → max-normal` (`0x7fe0…`),
  `te = −1022 → min-normal` (`0x0010…`),
  `te = −1074 → min-subnormal` (`0x…0001`), `te = −1075 → ±0` (underflow).
- A dense window `e ∈ [BIAS−1130, BIAS+1074]` exercises normal, subnormal and the
  class transitions; mantissas deliberately stress the low 7 bits (guard/sticky:
  `0x7F`, `0x40`, `0x3F`, exact half, etc.) — where the 59→52 rounding actually
  decides.
- The far field (`e` far from BIAS) and gf96-subnormals (e=0) exercise the
  overflow→±inf and underflow→±0 branches; plus a deterministic random fill
  (seed=20260724).
- A full exhaustive sweep (2^96 codes) is impossible — this is the same strictness
  tier as the FPGA conformance for wide formats (and as gf48).

## Tier and bounds (BINDING)

- This is **strict SW-bitexact** `[proven]` — NOT Tier-E (no run on AX7203
  silicon). Synth/PnR/flash on the board = `[REQUIRES USER ACTION]`, a separate
  epic (64-bit output, not the FP32 lineup).
- Horizon-A: live SW-bitexact snapshot 70→71, remaining promotable
  selfconsistent 5→4 (`gf128/256/512/1024` left).

## Lesson of this session

A wide signed exponent in RTL must not be sliced into a field directly:
`exp_field = E2_post[10:0] + 1023` breaks for negative E2 (the low-11-bit slice of
a two's-complement value is garbage → for E2=−1024 it yielded field=2047 → a
spurious overflow → +inf instead of a subnormal). The correct way: **signed sum
`E2_post + 1023` first, then the low-11-bit slice**, and do NOT add a redundant
`exp_field >= 2047` term to `is_overflow` (it duplicates `E2_post >= 1024` and is
harmful for negative E2). This class of bug (width/sign slicing) is exactly what
iverilog catches and a python transcription cannot (inv. #6).

## Files

- `conformance/gf96_bitexact_oracle.py` — witnesses A (mpmath) + B (integer), vector generation
- `conformance/gf96_vectors.hex` — 59050 vectors "<96-bit raw> <64-bit expected>"
- `fpga/openxc7-synth/gf96_decode_fp64.v` — RTL witness C
- `fpga/openxc7-synth/tb_gf96_decode_fp64.v` — iverilog testbench

## Reproduce

```bash
cd conformance && python3 gf96_bitexact_oracle.py    # A==B + writes vectors
cp gf96_vectors.hex /tmp/ && cd /tmp
iverilog -g2012 -o gf96_tb ../<repo>/fpga/openxc7-synth/gf96_decode_fp64.v \
                           ../<repo>/fpga/openxc7-synth/tb_gf96_decode_fp64.v
vvp gf96_tb                                            # C vs oracle
```
