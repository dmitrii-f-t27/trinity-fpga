# Finding — lns16 latent subnormal-flush bug (HW-proven Tier-E cell)

Discovered during the cross-format subnormal-bug audit (loop iter 9), extending
the takum32/64 fix story (`b537d0336`, `399bb0cf8`) to the rest of the logarithmic
family.

## What

`fpga/openxc7-synth/lns16_decode.v` (decode-HW, Tier-E proven) flushes ALL
subnormal-range results to signed zero:

```verilog
// line 165-166
else if (fp32_exp < 9'sd1)
    fp32_out = {sign, 8'h00, 23'h000000};       // underflow -> zero
```

But the golden (`conformance/lns16_decode_conformance_ax7203.py::golden_lns16`)
correctly produces subnormal FP32 values for inputs with `int_part ∈ [-128,-127]`
(value ∈ [2⁻¹²⁸, 2⁻¹²⁶] ⊂ FP32 subnormal range):

| code | golden | HW (current) | class |
|------|--------|--------------|-------|
| `0x4001` | `0x00202c7b` (2.955e-39) | `0x00000000` | **subnormal flush — wrong** |
| `0x4080` | `0x00400000` (5.877e-39) | `0x00000000` | **subnormal flush — wrong** |
| `0x4100` | `0x00800000` (1.175e-38) | normal path OK | — |

## Severity vs the takum fix

- **takum32/64**: only the `e2 = -150` boundary case was wrong (3-8 vectors of
  ~22k); fix was a 1-line guard `-149 → -150`.
- **lns16**: the ENTIRE subnormal range is flushed. Estimated ~256 codes
  (int_part = -128 and -127 × 128 frac entries each) produce wrong output. This
  is a ~0.8% latent error rate on the full code space (vs 0.03% for takum).

The bug is MORE severe than the one that motivated the takum fix, in a cell
already flashed and Tier-E-proven (the 64-vector conformance misses it — the
sample doesn't include subnormal-range codes).

## Why Tier-E missed it

The default `--n 64` conformance uses `corners + Random(31)` for lns16; none of
those draws hit the `int_part ∈ [-128,-127]` band. This is the same
small-sample blind spot that hid the takum subnormal bug — and is exactly what
the `--extended` flag (commit `5e63b519a`) was designed to structurally catch.
Once lns16 is re-flashed with the fix, `--extended` should be used for its
Tier-E proof.

## Fix (not yet implemented — needs re-synth + re-flash)

Mirror the takum subnormal-rounding path: replace the `fp32_exp < 1 -> zero`
flush with a proper subnormal computation
`sk = round(frac_mant >> (126 - int_part))` with RNE guard/round/sticky, handling
the round-up-to-min-subnormal (`0x00[8]000001`) and round-to-zero cases. The
lns16 datapath is a LUT + shift (no wide multiplies), so the added logic routes
trivially — no routing-opt needed, just correctness.

Scope: ~15-20 lines added to `lns16_decode.v`, structurally identical to the
subnormal block in `takum32_decode.v` (lines 63-75). Re-run the lns16 CI
workflow (already exists), flash, and Tier-E with `--extended`.

## Recommended priority

**P1** for the next loop's Option B (correctness sweep). The fix is mechanical
(clone the takum32 subnormal block with lns16's width parameters) and low-risk
on routing (lns16 is a small design). The result: lns16 goes from
"Tier-E-proven-with-~0.8%-latent-error" to "Tier-E-proven-and-actually-correct".

## Audit scope note

This audit covered the logarithmic family (takum8/16/32/64, lns8/16). Other
FP32-producing decoders (bf16, binary*, decimal*, fp4/6/8, etc. — 15+ files) use
DIRECT format conversions where the input's defined range typically doesn't
reach FP32 subnormals. A full audit of those for flush-to-zero at the subnormal
boundary is a separate task — but the logarithmic family (where dynamic range
naturally extends into subnormals) was the highest-risk set, and lns16 was the
only confirmed case beyond takum32/64.
