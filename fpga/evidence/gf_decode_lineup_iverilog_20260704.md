# GF decode-lineup — evidence of an independent iverilog-witness №2 (2026-07-04)

**Status format (BINDING honesty):** `[verified SW on iverilog]` ≠ `[measured on
silicon]`. This document records a **sim-bitexact** result on a real
Verilog-simulator (Icarus Verilog) with fixed-width semantics. This is NOT decode-HW:
the full 4/4 Tier-E chain (CI GREEN + bitstream SHA256 + UART `HW RESULT: N/N
bit-exact (fails=0)` @160000 baud + IDCODE `0x13636093`) on AX7203
(XC7A200T-2FBG484I) **has NOT been performed** and remains `[REQUIRES USER ACTION]`.

## What was verified

The parametric decoder `fpga/openxc7-synth/gf_decode_param.v #(N,E,M,BIAS,OUT_REG)`
→ IEEE binary32, the entire Phase-A GoldenFloat lineup (10 formats):

| fmt  | N  | E  | M  | BIAS | Witness №2 coverage             |
|------|----|----|----|------|-------------------------------|
| gf4  | 4  | 1  | 2  | 0    | exhaustive 16/16              |
| gf6  | 6  | 2  | 3  | 1    | exhaustive 64/64              |
| gf8  | 8  | 3  | 4  | 3    | exhaustive 256/256            |
| gf10 | 10 | 3  | 6  | 3    | exhaustive 1024/1024          |
| gf12 | 12 | 4  | 7  | 7    | exhaustive 4096/4096          |
| gf14 | 14 | 5  | 8  | 15   | representative + 5 classes    |
| gf16 | 16 | 6  | 9  | 31   | **exhaustive 65536/65536**    |
| gf20 | 20 | 7  | 12 | 63   | representative + 5 classes    |
| gf24 | 24 | 9  | 14 | 255  | representative + full-exp stress |
| gf32 | 32 | 12 | 19 | 2047 | representative + full-exp stress |

**Result:** 10/10 Phase-A `HW RESULT: N/N bit-exact (fails=0)` on iverilog
(gf16 — full exhaustive 65536/65536).

## Provenance (honestly)

- The witness-harness (golden-oracle on `fractions.Fraction`, Python bit-model of the RTL,
  vector generator, testbench) is reproducibly located in this PR:
  `fpga/witness/gf_decode/`.
- The green run `HW RESULT: N/N fails=0` was obtained on the **developer's local
  machine** (Icarus Verilog), working directory `/tmp/gf16_witness/` — outside
  CI and outside the sandbox. Raw iverilog logs are NOT embedded in this commit (we do not want to
  pass anything off as a reconstruction). Any reviewer can reproduce the result:

  ```bash
  cd fpga/witness/gf_decode
  python3 gen_vectors.py                       # (re)generate vectors/*.txt from golden
  # for each format: iverilog tb_gf_decode.v + gf_decode_param.v (with #(N,E,M,BIAS)),
  # then vvp -> expected "HW RESULT: N/N bit-exact (fails=0)"
  ```

- The Python model (`rtl_bit_model.py`) gives 10/10 PASS and serves as the **specification
  of the target semantics**, but by itself does NOT guarantee the Verilog-RTL — see below.

## Two fixed-width bugs caught ONLY by iverilog (not by Python)

Lesson of 04.07 (confirms the lesson of 28.06): a Python transcription with arbitrary-width int
physically does not catch Verilog fixed-width effects. The independent iverilog-witness №2
caught TWO real bugs that were invisible to the Python model:

1. **Fixed-width shift truncation** (the widen-fix). `pack_frac << (23-M)`, where
   `pack_frac` is declared `[M-1:0]`, was computed in an M-bit container →
   the high significant bits were truncated BEFORE the concatenation. First run of v1 RTL:
   gf16 exhaustive `HW RESULT: 1168/65536 bit-exact (fails=64368)` (~98% failure).
   **Fix:** first widen to the full result width, then shift
   (`wire [WIDE:0] pf_wide = {..0.., pack_frac}; norm_widen_result = pf_wide <<
   (23-M)`).

2. **Out-of-bounds bit-read in the FP32-subnormal packer.** `wire [M:0] sub_shifted`
   (for gf24 M=14 → 15 bits), but below it reads `sub_shifted[22:0]` → bits 22:(M+1)
   = out-of-bounds → X. Symptom: `dut=00Xxxxxx`. It triggers ONLY on the
   FP32-subnormal path (true_exp < −126, deep underflow), which gf16 (BIAS=31)
   never reaches — that is why gf16 remained clean after fix №1 and hid
   this bug; only gf24/gf32 (BIAS>127) exposed it. **Fix:**
   `wire [M:0] sub_shifted` → `wire [23:0] sub_shifted` (the RHS zero-extends,
   `[22:0]` reads valid zeros).

The widen-fix №1 alone is INSUFFICIENT — BOTH are needed. After both — green
10/10.

## Board invariants (for the subsequent synth/flash, not performed here)

- AX7203 = **XC7A200T-2FBG484I**, part `xc7a200tfbg484-2`, IDCODE `0x13636093`.
- Clock 200 MHz LVDS R4(+)/T4(−) → `IBUFDS`. UART @160000 baud.
- Toolchain openXC7 (Yosys + nextpnr + fasm2frames + xc7frames2bit),
  Docker `regymm/openxc7`.

## Links

- Anchor papers: arXiv:2606.05017 (a family by a single rule),
  arXiv:2606.09686 (format catalog).
- gf16-decode spec (issue #237): `fpga/gf16_decode_cell_TZ.md` — closed as
  a special case `#(N=16,E=6,M=9,BIAS=31)` of this generator.
- Catalog = 83 formats; this work = a 10-format FP32 GF-subfamily inside
  the catalog (Phase A). Phase B (gf48/gf64 → FP64) and Phase C (gf96…gf1024, SW-only) —
  are the next steps. No "first/only/best".
