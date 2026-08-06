# Corrections package — arXiv:2606.05017 and arXiv:2606.09686

**Status: DRAFT IN REPOSITORY. Submitted nowhere.** Whether to file any of this is
the author's decision. The package exists so that decision can be made once, from
evidence, instead of four times from memory.

**Verified:** passes 248–254, by scripts in this directory, against the corpus and
against the 226 comments of gHashTag/trinity-fpga#199.

---

## Summary

Seventeen quantitative claims have been recomputed. **Nine reproduce cleanly**,
one is a sensitivity note rather than an error, and **seven need action**.

| # | claim | paper | verdict |
|---|---|---|---|
| 1 | GF64 reaches 70.1% (359/512) | 2606.05017, and repeated in the catalog draft | **evidential** — no complete chain |
| 2 | "5/11 values flushed to zero" | 2606.05017, abstract + contributions | **wording** — body is correct |
| 3 | "GF16 preserves 8.7× more gradient updates" | 2606.09686, abstract | **sensitivity note**, not an error |
| 4 | "as in GF16 MUL's single-DSP multiplier" | 2606.09686, abstract + §flags | **factual** — no wrapper uses it |
| 5 | LUT_ADD ≈ 1.63 W², R² ≥ 0.97 | 2606.05017, §cost | **no subset fits** — c is a window, not a constant |
| 6 | 505 / 587 / 580 LUT | 2606.05017, lines 56 and 132 | **traced** — 505 is takum16's, and the 75 does not reproduce |
| 7 | "seven formats across seven workloads" | 2606.05017, abstract | **not reproducible** — six of the seven workloads exist in no script |
| 8 | "six conformance packs", including E8M0 | 2606.09686 abstract, and its erratum | **closed** — the E8M0 oracle and packs now exist |

What reproduces, for context: the 2.4M vector count (2,442,533), 41 decode cells,
10 GF compute formats, FP16 losing 5 of 11 dynamic-range values, GF16 losing 1,
the BF16 and GF16 noise floors (7.9% and 63.7% against 7.3% and 63.9%), and the
LUT table across twelve measurements with a largest deviation of 56 LUTs. Details
and tools in `research/PAPER_CLAIM_VERIFICATION.md`.

---

## 1. GF64 at 70.1% (359/512) — evidential

Full analysis: `research/ERRATUM_arXiv_2606.05017_gf64_claim.md`.

The figure is **not invented**. Seventeen comments investigate GF64 carefully, one
of them retracting an earlier theory. But no single GF64 comment carries all four
Tier-E links, and 359/512 is the highest of four silicon results spanning
19.2%–70.1%, from the build the next comment's own table labels "shift-reg
(buggy)". Every build with that path fixed scored lower.

It sits inside an item ending *"Each ships with a full evidence chain."*

**Proposed:** drop the aside, or restate it as an open timing-closure problem
rather than a cell. Suggested wording in the erratum file.

## 2. "5/11 values flushed to zero" — wording

Verified with `research/audit_arithmetic_claims.py` against `ieee_ref` and
`gf_ref`:

| value | FP16 (E=5) |
|---|---|
| 1e-10, 1e-8 | flush to zero |
| 1e-6 … 1e4 | representable |
| 1e6, 1e8, 1e10 | **overflow to infinity** |

Five of eleven are lost — the count is right in both places. Two flush to zero;
three fail at the **opposite end** of the range. The body's *"loses 5/11"* is
correct; only the abstract and the contributions list misstate the mechanism.

**Proposed:** in the abstract and contributions list, replace "flushed to zero"
with "lost" or "outside the representable range".

## 3. "8.7× more gradient updates" — sensitivity, not an error

63.9 / 7.3 = **8.75×**, which rounds to 8.7. The claim follows from the paper's
own numbers.

Recomputed from the oracles with the paper's own protocol — 2000 sequential steps
from w=0.5, updates from N(1e-4, 1e-3), re-quantised each step, five seeds — the
preserved fractions are 7.9% and 63.7%, giving **8.06×**.

Both are correct about their inputs. The ratio is sensitive to the BF16
denominator, which is the smaller and noisier of the two numbers.

**Proposed:** nothing is wrong. If a revision is being made anyway, "roughly 8×"
is more robust than "8.7×" to the seed and step count.

## 4. "as in GF16 MUL's single-DSP multiplier" — factual

`fpga/openxc7-synth/gf_mul_dsp_param.v` exists and does instantiate `DSP48E1`.
**No wrapper instantiates it.** The only two files referencing it are itself and a
comment in `gf_mul_param.v` saying the DSP mapping lives elsewhere.

`corona_compute_gf16_mul_ax7203.v` instantiates `gf_mul_param` — the LUT-only
version. That is consistent with `-nodsp` and with the 586/602 LUT measurement,
and inconsistent with GF16 MUL being the example of explicit DSP instantiation.

**Proposed:** either cite `gf_mul_dsp_param` as an available-but-unused path, or
drop "as in GF16 MUL" and keep the general statement that DSP48E1 is used only
when explicitly instantiated.

---

## 5. The W² cost model — the coefficient is a window, not a constant

Fitted through the origin to the paper's own published tables:

| set | n | c | R² |
|---|---|---|---|
| ADD, GF4–GF24 (the stated range) | 9 | 1.588 | 0.9371 |
| ADD, GF4–GF32 | 10 | 1.350 | 0.9272 |
| **ADD, GF4–GF48** | **11** | 1.245 | 0.9815 |
| ADD, all measured | 14 | 0.928 | 0.9951 |
| MUL, GF4–GF24 | 9 | **2.089** | **0.9770** |

**No set reproduces c_ADD = 1.63 with R² ≥ 0.97.** The only set with exactly
eleven points — the count the paper cites — gives c = 1.245.

The reason is visible in the per-point ratio LUT/W², which falls monotonically
rather than holding constant:

| W | 4 | 6 | 8 | 12 | 16 | **20** | 24 | 32 | 64 | 128 |
|---|---|---|---|---|---|---|---|---|---|---|
| c | 0.94 | 2.78 | 2.67 | 1.97 | 1.90 | **1.61** | 1.42 | 1.21 | 1.05 | 0.91 |

**1.63 is approximately the value at W = 20**, not a property of the family.

With a free exponent, `LUT = a·W^b`:

| | a | b | R² |
|---|---|---|---|
| ADD, all 14 measured | 3.194 | **1.754** | 0.9746 |
| MUL, GF4–GF32 | 0.791 | **2.361** | 0.9044 |

ADD is **sub-quadratic** over the measured range and MUL is **super-quadratic**.
A shared W² model with a single coefficient is a compromise between them rather
than a fit to either.

**Proposed:** state the fitting window with the coefficient, or report the fitted
exponents. As written, "1.63 W², R² ≥ 0.97, 11 measured points" does not
correspond to any subset of the published table.

## 6. 505 / 587 / 580 LUT — traced, and one entry does not reproduce

The three numbers come from `research/COMPLETE_LUT_TABLE.md`'s "additional cores"
table, and tracing them there makes the problem precise rather than merely
inconsistent:

| core | table | measured here | |
|---|---|---|---|
| Ternary MAC-16 | 55 LUT | **55** | exact |
| GF Sqrt | 128 LUT, 8 DSP | **128 LUT, 8 DSP** | exact |
| GF Div | 207 LUT | **207** | exact |
| **GF Quire** | **75 LUT, 0 DSP** | **1063 LUT, 0 DSP** | **14×** |
| takum16 native MUL | 505 LUT | — | |
| GF16 | 485 ADD / 587 MUL | 490 / 602 | ordinary build drift |

Three of the four modules reproduce **exactly**, which is what makes the fourth
meaningful. The GF Sqrt row needed DSP inference left on — forcing `-nodsp` gives
4818 LUTs, and that was my error, not the table's.

So:

* **505 is takum16's multiply** in the source table, not GF16's. GF16's multiply
  is 587 there.
* Line 132's "580 LUT (505 multiply + 75 Quire)" therefore uses takum16's
  multiply figure for a GF16+ MAC, together with a Quire figure that does not
  reproduce.
* Line 56's "GF16 multiply-with-Quire (505 LUT) … plain GF16 multiply is 587 LUT"
  has a Quire with negative area under any reading.

**Proposed:** re-measure `gf_quire_param` and restate the MAC total. If the Quire
is genuinely 1063 LUTs, the GF16+ MAC is roughly 1650, not 580.

## 7. "Seven formats across seven workloads" — six of the workloads are not here

The abstract's central result is that GF16 is *the minimum-width IEEE-style format
that passes all seven tests*. The seven are named as four ML — matrix multiply,
gradient accumulation, dynamic range, attention softmax — and three hold-out —
convolution, polynomial evaluation, linear solve.

`research/format_benchmark.py`, which the paper cites as "the benchmark script",
implements **four suites**: `arithmetic`, `dynamic_range`, `cancellation`,
`edge_cases`. Only `dynamic_range` is one of the seven.

**Matrix multiply, gradient accumulation, attention softmax, convolution,
polynomial evaluation and linear solve appear in no script in the repository.**

### What implementing them showed

All seven are now runnable: `research/workload_matmul.py` (matrix multiply),
`research/workload_suite.py` (gradient accumulation, attention softmax,
convolution, polynomial evaluation, linear solve), and `dynamic_range` in
`format_benchmark.py`.

The first numbers I produced were wrong, and the correction matters more than the
original. Dividing the error by the exact **result** makes it explode wherever a
sum of products cancels — matrix multiply reported BF16 at 184%, and convolution
reported ≈54% for BF16, GF14 and GF16 *alike*, three formats sharing one number
that belonged to the inputs. Dividing instead by the **scale of the work**,
`Σ|a·b|`, is the standard normwise form and separates conditioning from precision.

Normwise, worst trial / median trial:

| workload | BF16 (M=7) | GF14 (M=8) | GF16 (M=9) | FP16 (M=10) |
|---|---|---|---|---|
| matmul, uniform[-1,1] | 0.71 / 0.49 | 0.31 / 0.26 | 0.14 / 0.12 | 0.06 / 0.06 |
| matmul, normal(0,1) | 1.16 / 0.52 | 0.43 / 0.27 | 0.25 / 0.14 | 0.09 / 0.06 |
| convolution | 0.84 / 0.54 | 0.30 / 0.24 | 0.17 / 0.12 | 0.07 / 0.06 |
| gradient accumulation | 2.68 / 1.93 | 1.98 / 0.79 | 1.15 / 0.44 | 0.74 / 0.19 |
| attention softmax | 2.57 / 1.46 | 0.92 / 0.59 | 0.44 / 0.30 | 0.30 / 0.16 |
| polynomial | 1.04 / 0.29 | 0.72 / 0.17 | 0.23 / 0.05 | 0.19 / 0.09 |
| linear solve | 14.76 / 1.11 | 8.31 / 0.68 | **0.93** / 0.45 | **1.10** / 0.26 |

**The error halves per mantissa bit** — 0.71, 0.31, 0.14, 0.06 across M = 7, 8, 9,
10. That is 2⁻ᴹ, and it is what precision looks like once conditioning is removed.

**There is no threshold at M ≥ 9.** The curve is smooth. A threshold exists only
once someone fixes an error budget, and none is published — so "M ≥ 9" is a choice
of budget presented as a property of the workload.

Two results survive as genuine, and both are about **range**, not mantissa:
GF14 scores 84.85% on mixed-scale matmul because E=5 lets products underflow; and
linear solve has GF16 beating FP16 on the worst case, 0.93 against 1.10, despite
one fewer mantissa bit, because E=6 beats E=5.

**Proposed:** commit the seven-workload harness, and state the error budget that
turns a smooth 2⁻ᴹ curve into the threshold M ≥ 9. The feasible corner (E=6, M=9),
and with it the φ-ratio result, rests on that budget being stated.

## 8. "Six conformance packs" — five of them are packs

The 2606.09686 abstract names six: GF16, MXFP4 element, BF16, FP8 E4M3, FP8 E5M2,
and E8M0 block scale. Five are present in `conformance/vectors/`. **E8M0 is not.**

No file matches `e8m0` there, and no oracle in `conformance/*_ref.py` carries an
`e8m0` format key.

What E8M0 *does* have is a conformance **host**,
`conformance/e8m0_decode_conformance_ax7203.py`, whose header states its golden is
*"re-implemented from the E8M0 spec, NOT copied from the RTL"* — plus RTL wrappers
and a complete-chain Tier-E decode cell.

**So the hardware claim stands.** What is missing is the pack and the oracle, not
the evidence.

This also touches the existing erratum,
`research/ERRATUM_arXiv_2606.09686_catalog_count.md`, which says:

> the presence of a conformance pack for E8M0 is correct and remains in force —
> the pack covers the block-scale component

There is no pack file to remain in force.

**Closed in pass 266.** `conformance/e8m0_ref.py` is the missing oracle and
`conformance/vectors/e8m0_add.json` and `e8m0_mul.json` are the missing packs,
65,536 vectors each — the format is 8 bits, so both are exhaustive over all
256×256 operand pairs. The oracle's self-test holds it to the host's independent
golden on all 256 codes and passes 10/10.

No `e8m0_sub.json`: E8M0 has no sign bit and no zero, so negation does not exist
and SUB is undefined. `negate_raw` now says so, the same way it already did for
unsigned integers. Without that it fell through to the default branch, flipped
bit 7 — which for E8M0 changes the *exponent* — and produced a 65,536-vector pack
of nonsense, which is what a first run actually wrote before it was caught.

**Still proposed:** amend the erratum's sentence. It said a pack "remains in
force" when none existed; now one does, but the sentence was not true when
written.

---

## Not checkable from this repository

**"72 of 83 formats carry an independent executable oracle."** The catalog
membership list is `formats_catalog.t27` in the **t27** repository, not present
here. The oracles carry **84** format keys, several of which are known not to be
catalog rows — `fp16_e6m9` and `fp24_7m16` exist only in the silicon-sprint packs,
`bf16`/`bfloat16` is an alias pair. **84 neither confirms nor refutes 72.**

## Two errors of mine, recorded rather than omitted

1. **LUT drift.** Pass 250 reported a +22% to +79% deviation from the published
   LUT table. That was a parser — yosys `stat` prints three blocks and my counter
   summed across a boundary. Retracted in pass 251; the corrected table shows the
   numbers reproduce.
2. **Noise-floor protocol.** My first run held the weight fixed instead of walking
   it, giving 17.2% and 71.6%.

Both are the same mistake: measuring a reasonable-sounding neighbour of the thing
the method describes. Neither reached a published claim.

## How to regenerate

```
python3 research/audit_paper_claims.py --comments <cached #199 json>
python3 research/audit_arithmetic_claims.py
python3 research/audit_lut_table.py
```
