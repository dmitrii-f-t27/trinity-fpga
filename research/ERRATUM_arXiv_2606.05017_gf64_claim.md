# Erratum draft — arXiv:2606.05017 (GoldenFloat robustness analysis)

**Status: DRAFT IN REPOSITORY. Not submitted anywhere.** Whether to file this is
the author's decision; this file records the finding and the evidence so that
decision can be made from facts rather than from memory.

**Article:** D. Vasilev, [arXiv:2606.05017](https://arxiv.org/abs/2606.05017).
**Type of correction:** evidential — a figure quoted inside a full-evidence-chain
claim whose own sources do not carry that chain.
**Verified:** pass 249, by `research/audit_paper_claims.py` against the 226
comments of gHashTag/trinity-fpga#199.

---

## 1. The sentence

`research/arxiv_submission/paper.tex`, contributions list:

> **A breadth benchmark.** ~41 of 83 catalog formats carry at least one bit-exact
> decode cell on silicon (41 decode ports); of these, 10 GF formats (GF4–GF32)
> additionally carry bit-exact compute cells (ADD/MUL)—**GF64 reaches 70.1%
> (359/512) due to a timing-closure issue.** Each ships with a full evidence
> chain: CI synthesis → bitstream SHA-256 → JTAG flash → UART verify against an
> independent golden oracle.

Three of the four numbers in that item check out exactly against the corpus:

| claim | paper | corpus |
|---|---|---|
| vectors (elsewhere in the paper) | 2.4M | 2,442,533 |
| decode cells | ~41 of 83, 41 ports | 41 distinct formats |
| GF compute formats | 10 | 10 distinct widths |

The GF64 aside is the one that does not.

## 2. What is actually behind 359/512

**It is not an unsupported number.** Seventeen comments in #199 mention GF64, and
several are a careful, self-correcting investigation — including one titled
*"RETRACTION: 'fp32 M=23 boundary' was WRONG"*. The 70.1% figure comes from
*"GF64 ADD: HAS_INF(0) fix + provenance — honest silicon result"*, which reports:

| test | result |
|---|---|
| iverilog (core, sequential) | 6/6 |
| Python bit-model, 1544 vectors | 1544/1544 |
| **silicon, 512 vectors** | **359/512 (70.1%)** |

and attributes the gap to the wrapper rather than the core — which is what the
paper's "timing-closure issue" restates.

## 3. Two problems, both narrow

### 3.1 It does not carry the chain the same sentence promises

The paper's own definition is four links in one place: a public CI run URL, the
bitstream SHA-256, a UART `HW RESULT: N/N bit-exact` line, and the matching
IDCODE. Across all seventeen GF64 comments, **no single one carries all four**:

| comment | CI URL | full SHA-256 | `HW RESULT:` line | IDCODE |
|---|---|---|---|---|
| Tier-E smoke: GF64 + GF128 ADD | ✅ | ✅ | — | ✅ |
| GF64 ADD: HAS_INF(0) fix (the 359/512 one) | build number only | truncated `634b4c09…` | score, not the line | ✅ |
| GF64 ADD TX race fix | — | — | score, not the line | — |
| GF64 ADD: barrel shifter clamp | — | — | — | — |

The closest is three of four. The one that carries the quoted figure has a
**truncated** SHA and a build number rather than a URL.

### 3.2 The figure is the best of four, from the build later called buggy

The follow-up comment's own synthesis matrix:

| build | TX pattern | score |
|---|---|---|
| Original | **shift-reg (buggy)** | **359/512 (70.1%)** |
| TX fix + abc9 | buffer+mux | 285/577 (49.4%) |
| TX fix, no abc9 | buffer+mux | 111/577 (19.2%) |
| barrel-shifter clamp | buffer+mux | 282/577 (48.9%) |

So 70.1% is the highest of four silicon results spanning 19.2%–70.1%, and it
comes from the build that the next comment's table labels as having a buggy TX
path. Every build with that path *fixed* scored lower.

## 4. Proposed correction

Either of these is defensible; the second is closer to what the evidence supports.

1. **Drop the aside.** The item's subject is formats that carry a full evidence
   chain. GF64 does not, so removing it makes the sentence true as written.
2. **Restate with the qualifier.** For example:

   > …10 GF formats (GF4–GF32) additionally carry bit-exact compute cells
   > (ADD/MUL). GF64 ADD is *not* among them: its core passes 6/6 in simulation
   > and 1544/1544 against the bit-model, while silicon results across four
   > synthesis variants range from 19.2% to 70.1%, and no single run carries the
   > complete four-link chain. We report it as an open timing-closure problem
   > rather than a cell.

## 5. What does NOT change

- The 41 decode cells, the 10 GF compute formats and the 2.4M vector count all
  hold exactly.
- The GF64 investigation itself is sound work and should stay cited; the issue is
  only where its number is placed.
- Nothing here affects arXiv:2606.09686 or its existing 84→83 erratum.

## 6. A correction to my own previous statement

Pass 248 reported "zero complete-chain comments mention gf64" — true — but framed
it in a way that reads as *the number is unsupported*. It is supported, by
evidence that does not meet the four-link form. The defect is a mismatch between a
figure and the chain claimed for it, not an invented number.
