# Finding — catalog-wide subnormal-flush bug (6 Tier-E cells suspected)

Cross-reference of (RTL flush-to-zero pattern) × (golden subnormal production)
across all FP32-producing decoders, extending the lns16 fix (commit `bffc7a2ab`)
to the full catalog.

## Method

1. **RTL scan**: grep each `*_decode.v` for `exp < 1 -> zero` flush pattern,
   excluding files that also contain subnormal-rounding logic (`sk =`, `sv = >>`).
2. **Golden scan** (`tools/fpga_subnormal_audit.py`): sample inputs across each
   format's range, count how many produce FP32 subnormals (`exp_field==0 &&
   mantissa!=0`) in the mpmath golden.
3. **Verdict**: a format is SUSPECTED if it has the RTL flush pattern (step 1).
   A format is CLEAN if it has no flush pattern OR if it has explicit subnormal
   rounding. Random-sample "0 subnormals" for large-range formats is
   INCONCLUSIVE (sampling gap — their subnormal band is narrow).

## Cross-reference table

| format | RTL flush-pattern | golden produces subnormals? | verdict |
|--------|-------------------|-----------------------------|---------|
| lns16 | (was flush, **FIXED** `bffc7a2ab`) | yes (3 in sweep) | **fixed** |
| **binary64** | **yes (line 41)** | sampling gap | **SUSPECTED** |
| **binary128** | **yes** | sampling gap | **SUSPECTED** |
| **ibm_hfp32** | **yes (line 61)** | sampling gap | **SUSPECTED** |
| **ibm_hfp64** | **yes** | sampling gap | **SUSPECTED** |
| **vax_g** | **yes** | sampling gap | **SUSPECTED** |
| **posit32** | **yes** | sampling gap | **SUSPECTED** |
| binary32 | no | yes (522, handled) | clean |
| decimal32/64/128 | no / has rounding | decimal64: 39 (rounded) | clean |
| vax_d, vax_f | no | — | clean |
| ms_mbf32/64 | no | — | clean |
| lns8 | n/a (Q8.8 fixed-point output) | — | clean |

## What "suspected" means

The 6 suspected formats have `else if (exp_final < 1) fp32_out = zero` in their
RTL — the SAME flush-to-zero that lns16 had. Their dynamic ranges all extend
below FP32's smallest normal (2⁻¹²⁶):
- binary64 min: 2⁻¹⁰⁷⁴  → FP32 subnormal band (2⁻¹⁴⁹..2⁻¹²⁶) is within range
- binary128 min: 2⁻¹⁶⁴⁹⁴ → same
- ibm_hfp32 min: 16⁻⁶⁴ ≈ 10⁻⁷⁸ → same
- ibm_hfp64 min: 16⁻⁵² ≈ 10⁻⁶³ → same
- vax_g min: 2⁻³⁴² (G-float) → same
- posit32 min: depends on regime (tapered), reaches well below 2⁻¹²⁶

So subnormal-producing inputs EXIST for each; the flush makes the HW produce
signed zero where the golden correctly produces a subnormal. Latent correctness
gap in already-flashed Tier-E cells.

## Why Tier-E missed it (same root cause as lns16)

Each format's default `--n 64` conformance uses corners + a seeded random draw
that doesn't hit the format's specific subnormal band. The 64-vector Tier-E
proof passes despite the bug.

## Fix template (per format)

Mirror commit `bffc7a2ab` (lns16): replace the flush with a subnormal rounding
path. For formats with a fixed implicit-1 mantissa (binary64/128, ibm_hfp,
vax_g), the shift amount is variable (`sh = 1 - exp_final`, can be up to ~126
for binary64) — requires a barrel shifter + computed sticky bit, more involved
than lns16's 2-entry case. For posit32 (regime-based), the structure differs.

Suggested fix order (by impact + ease):
1. **ibm_hfp32** — smallest datapath after lns16; mantissa is 24-bit fraction.
2. **vax_g** — similar magnitude to binary64 but simpler mantissa.
3. **binary64** — canonical, widest use, but needs the variable-shift path.
4. **binary128, ibm_hfp64** — wide, lower traffic.
5. **posit32** — regime-based structure needs its own analysis.

Each fix is one loop of work (RTL + iverilog verify on subnormal-band vectors +
re-synth + re-flash + Tier-E with `--extended`).

## Audit reproducibility

```
python3 tools/fpga_subnormal_audit.py        # golden-side scan
# RTL cross-reference: see the table above (grep for 'exp.*<.*1.*zero')
```

The audit tool has a known sampling gap for large-range formats — a targeted
follow-up should construct each format's subnormal-band inputs explicitly
(analogous to lns16's 0x4000+ sweep) to definitively confirm the 6 suspects.

## CORRECTION (loop iter 12) — retraction of the "6 suspects"

**The "6 suspected cells" claim above is RETRACTED.** Follow-up verification
showed all 6 are CLEAN. The audit methodology (RTL-pattern-only) was insufficient.

The definitive test is whether the GOLDEN itself flushes subnormals. Cross-check
of each conformance golden:

| format | golden flushes subnormals? | verdict |
|--------|---------------------------|---------|
| binary64 | YES (`exp < 1 -> return 0`) | CLEAN (HW matches golden) |
| binary128 | YES | CLEAN |
| ibm_hfp32 | YES (line 30) | CLEAN |
| ibm_hfp64 | YES | CLEAN |
| vax_g | YES | CLEAN |
| posit32 | YES | CLEAN |
| **lns16** | **NO (produces real subnormals)** | **the ONLY confirmed bug (fixed bffc7a2ab/89135c37e)** |

The project's convention for binary64/128, ibm_hfp32/64, vax_g, posit32 is to
flush FP32 subnormals (the golden defines it that way; the HW implements the
same convention). There is no HW-vs-golden mismatch there.

**The subnormal-flush bug class is UNIQUE to lns16** in this catalog -- it was
the only format where the golden produces real FP32 subnormals but the HW
flushed them. The fix (commits bffc7a2ab + 89135c37e yosys-compat) stands and
is the sole correctness improvement from this audit.

## Methodology lesson for the audit tool

`tools/fpga_subnormal_audit.py` currently flags "golden produces subnormals" --
which is necessary but NOT sufficient. The correct test is the INTERSECTION:
(golden produces subnormals) AND (HW flushes them). For 6 of 7 candidates the
golden flushes too, so there is no mismatch. The tool should be extended to
read the golden's flush behavior (or run golden-vs-HW-model on the subnormal
band) before flagging. The ibm_hfp32 fix attempt (779 regressions, reverted)
was the costly demonstration of this gap.
