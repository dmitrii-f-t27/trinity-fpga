# gf_mul_param timing risk — same priority-encoder failure mode as the adder

**Status:** Audit finding (Track F)
**Date:** 2026-07-14
**Scope:** `fpga/openxc7-synth/gf_mul_param.v`
**Verdict:** For `MANT_BITS > ~24` (GF64 and wider), `gf_mul_param.v` will
**fail timing on AX7203 (XC7A200T) at CFGMCLK** for the same root cause that
already failed the adder: a wide, unclamped, unpipelined combinational MSB
search. The narrower formats (GF4–GF32) that are currently on silicon are
unaffected; the risk is for any future GF64+ port.

---

## 1. The offending structure

`gf_mul_param.v` finds the most-significant set bit of the product with a
combinational priority encoder written as a loop:

```verilog
// gf_mul_param.v:137-139
msb = -1;
for (k = PW-1; k >= 0; k = k - 1)
    if (p[k] && msb == -1) msb = k;
```

where the product width is

```verilog
// gf_mul_param.v:57
localparam PW = 2*(MANT_BITS+1);
```

Synthesis turns this loop into a **PW-way priority encoder** over the full
product word. There is **no clamp and no pipeline register** on this path — the
MSB feeds directly into the exponent correction
(`gf_mul_param.v:147` `exp_field = er + (msb - 2*MANT_BITS)`), the mantissa
extraction (`:159-161`), the guard/round/sticky extraction (`:162-167`), and
the denormal pack decision (`:152`). The whole normalize+round+pack cone hangs
off `msb` in a single clock cycle.

A second, softer version of the same hazard is the sticky OR-reduction:

```verilog
// gf_mul_param.v:165-167
for (k = 0; k <= PW-1; k = k + 1)
    if (k < msb - MANT_BITS - 2 && k >= 0)
        sticky = sticky | p[k];
```

This is a flat OR tree (log-depth) and is comparatively benign, but it still
scales with `PW` and adds to the same combinational cone.

---

## 2. Why this is the adder's bug again

The GF64 **adder** already failed timing on this exact hardware for this exact
reason. The repo documents it in multiple places:

- `README.md:66` — *"GF64 timing closure failure — root cause identified …
  (a) a 43-bit barrel shifter driven by a 25-bit amount, now clamped to 6 bits
  (`MANT_BITS+4`); **(b) an 8-branch priority encoder over 64-bit data, still
  too deep for CFGMCLK**. Definitive fix is a 2-stage pipeline."*
- `.trinity/experience/wave_2026_07_14_wave3.md:91-98` — *"GF32 (23-bit barrel
  shifter) meets timing → 11392/11392 bit-exact. **GF64 (43-bit barrel shifter)
  fails timing → ~50-70% pass rate.** Fix: pipeline the adder."*
- `research/CATALOG_PAPER_DRAFT.md:174-178, 271-278` — GF64 ADD reaches only
  **359/512 (70.1%)** on silicon due to the barrel-shifter / priority-encoder
  depth; GF32 passes.
- `research/arxiv_submission/submission_checklist.md:14` — GF64 is reported as
  *"70.1% silicon (359/512), timing-closure issue in the 43-bit barrel
  shifter" — NOT bit-exact.*

The adder was mitigated by **clamping** the barrel-shifter amount to
`MANT_BITS+4` (`gf_adder_param.v:83-85`):

```verilog
// Clamp shift amount … reduces the barrel shifter from EXP_BITS+1 mux levels
// to log2(MANT_BITS+5) levels — critical for GF64+ timing closure.
wire [7:0] ediff_shift = (ediff > (MANT_BITS+4)) ? (MANT_BITS+4) : ediff[7:0];
```

…which helped but did **not** fully close timing (the priority-encoder half of
the path remained), so the documented definitive fix is a 2-stage pipeline.

`gf_mul_param.v` has **neither** mitigation: no clamp on the MSB search, and
no pipeline register. Its MSB-search cone is over `PW = 2*(MANT+1)` bits —
**wider than the adder's `MANT+4`-bit barrel operand for the same format** —
so any format that breaks the adder breaks the multiplier at least as badly.

---

## 3. Priority-encoder depth per GF format

`PW = 2*(MANT_BITS+1)` is the priority-encoder width (the loop scans `k` from
`PW-1` down to `0`). Depth is compared against the adder's documented
boundary: adder barrel ≤ ~28 bits (GF32, `MANT+4`) meets timing at CFGMCLK;
adder barrel = 43 bits (GF64) fails.

| Format | MANT_BITS | PW (mul priority-encoder width) | Adder barrel (MANT+4) | Mul timing on AX7203 |
|--------|-----------|---------------------------------|-----------------------|----------------------|
| GF4    | 2         | 6                               | 6                     | OK                   |
| GF6    | 3         | 8                               | 7                     | OK                   |
| GF8    | 3-4       | 8-10                            | 7-8                   | OK                   |
| GF12   | ~6        | ~14                             | ~10                   | OK                   |
| GF16   | 9         | 20                              | 13                    | OK (proven Tier-E)   |
| GF20   | 12        | 26                              | 16                    | OK (proven Tier-E)   |
| GF24   | ~14       | ~30                             | ~18                   | borderline / OK      |
| GF32   | 23-24     | 48-50                           | 27-28                 | marginal (proven with `-nodsp`) |
| GF64   | ~39-52    | **80-106**                      | 43 (fails)            | **FAILS**            |

Notes:
- The GF4–GF32 MUL cells are on silicon and Tier-E proven
  (`CATALOG_MATRIX_83.md:27` — "MUL 10/10"). GF32 MUL required the `-nodsp`
  build flag, which is itself a sign the combinational cone is already at the
  timing edge.
- GF64 MUL has **not** been put on silicon. Extrapolating from the adder
  (whose 43-bit barrel fails) and from the table (mul's priority encoder at
  GF64 is 80-106 bits wide — roughly 2× the adder's failing path), GF64 MUL
  **cannot** close timing at CFGMCLK in its current form.
- The multiplier also has a barrel-shift inside `pack_denorm`
  (`gf_mul_param.v:220` `mant_out = (pr << p_sh)` and `:232` `mant_out = pr >> sh`),
  driven by an exponent-derived amount. This is a second, independent
  timing-critical shifter of the same family as the adder's, and it is also
  unclamped.

---

## 4. Expected impact

- **GF4–GF32 (MANT_BITS ≤ ~24):** no change. These already meet timing and are
  Tier-E proven. The warning does not affect any shipped cell.
- **GF64 and wider (MANT_BITS > ~24):** the multiplier will behave like the
  adder did — passes iverilog simulation (functionally correct) but fails
  timing on AX7203, producing a silicon pass rate well below 100% (the adder
  hit ~70%; the mul's deeper cone would be equal or worse). Any "GF64 MUL"
  claim built on the current core would be non-bit-exact for the same reason
  GF64 ADD is non-bit-exact.

---

## 5. Recommendation

Apply the **same fix already mandated for the adder**, in priority order:

1. **Clamp the MSB-search width.** The product of two normalized significands
   has its MSB in only two adjacent positions (`2*MANT+1` or `2*MANT`); for
   denormal operands the MSB can be lower, but never below the sticky region.
   Bound the search to the meaningful window (analogous to the adder's
   `ediff_shift` clamp) so the priority encoder does not span the full `PW`.
2. **Add a pipeline register after the MSB search** (MSB → register →
   normalize+round+pack). This is the adder's documented "definitive fix"
   (`README.md:66`) and is the only guaranteed cure for GF64+. Cost: one extra
   latency cycle, identical handshake discipline.
3. **Clamp / pipeline the `pack_denorm` barrel shifter** (`gf_mul_param.v:220,
   232`) the same way, since it is an independent timing path of the same
   shape.
4. **Re-prove on silicon** with the two-oracle discipline (Python `Fraction`
   faithful transcription + iverilog from-spec reference, as used for ADD/MUL
   in `gf_adder_param` / `gf_mul_param`) before asserting any GF64 MUL
   Tier-E claim. Until then, any GF64 MUL result must be reported as
   "timing-limited, not bit-exact" exactly as GF64 ADD is today.

---

*Honesty note: Vasilev, ORCID 0009-0008-4294-6159. The narrow-format MUL cells
(GF4–GF32) are bit-exact on silicon; this document is a forward-looking timing
risk for GF64+ ports only.*
