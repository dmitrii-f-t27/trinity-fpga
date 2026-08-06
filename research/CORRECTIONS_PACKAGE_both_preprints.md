# Corrections package — arXiv:2606.05017 and arXiv:2606.09686

**Status: DRAFT IN REPOSITORY. Submitted nowhere.** Whether to file any of this is
the author's decision. The package exists so that decision can be made once, from
evidence, instead of four times from memory.

**Verified:** passes 248–254, by scripts in this directory, against the corpus and
against the 226 comments of gHashTag/trinity-fpga#199.

---

## Summary

Eleven quantitative claims were recomputed. **Nine reproduce.** Four items below
need action, and only two of them are errors.

| # | claim | paper | verdict |
|---|---|---|---|
| 1 | GF64 reaches 70.1% (359/512) | 2606.05017, and repeated in the catalog draft | **evidential** — no complete chain |
| 2 | "5/11 values flushed to zero" | 2606.05017, abstract + contributions | **wording** — body is correct |
| 3 | "GF16 preserves 8.7× more gradient updates" | 2606.09686, abstract | **sensitivity note**, not an error |
| 4 | "as in GF16 MUL's single-DSP multiplier" | 2606.09686, abstract + §flags | **factual** — no wrapper uses it |

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
