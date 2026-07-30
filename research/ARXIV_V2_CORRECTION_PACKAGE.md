# arXiv v2 correction package — 2606.05017 and 2606.09686

> Produced 2026-07-31 by a verification pass over the two published abstracts
> against the live artefacts. Every claim below carries how it was verified.
> Nothing here is asserted from memory or from a state file.
>
> **This is a prepared package, not a submission.** Replacing an arXiv entry
> needs the author's arXiv credentials — see §9.

## 0. Method

Abstracts were pulled verbatim from the arXiv API
(`https://export.arxiv.org/api/query?id_list=<id>`). Artefact state was read from
`gHashTag/t27` over the GitHub API (tree + file contents + commit history for
`conformance/vectors`). Third-party versions were checked against their own
registries. No claim below rests on a repo state file.

---

## 1. Paper A — arXiv:2606.05017 (GoldenFloat)

*"GoldenFloat: A Phi-Derived Static-Split Floating-Point Family from GF4 to GF1024
with a Lucas-Exact Integer Identity"*, submitted 2026-06-03.

### 1.1 CRITICAL — the abstract asserts fabricated dies exist

Published abstract, final sentence:

> An RTL-correctness erratum dated 2026-05-31 is reported in Section 5.5; **the
> fabricated TTSKY26b dies carry the defective multiplier portfolio**, and the
> corrected generator is the regeneration baseline.

This states that fabricated TTSKY26b dies exist. The binding project fact is that
the silicon track was **cancelled** — no dies were fabricated. The identical claim
has already been removed from the local paper sources in
`gHashTag/trinity-papers-ru` PR #17 (commit `925bdf6d`, *"убрать чипы/кремний из
ВСЕХ статей"*), whose replacement wording is reused verbatim below so the arXiv
entry and the repository agree.

**Proposed replacement:**

> An RTL-correctness erratum dated 2026-05-31 is reported in Section 5.5; **an
> early RTL multiplier generator carried a defect**, and the corrected generator
> is the **design** baseline.

Two substantive edits: `the fabricated TTSKY26b dies carry the defective
multiplier portfolio` → `an early RTL multiplier generator carried a defect`, and
`regeneration baseline` → `design baseline`. This is the highest-priority item in
this package: it is a factual claim about physical artefacts, live on a public
preprint.

> Section 5.5 of the paper body must be checked for the same wording — the
> abstract is the visible surface, not the only occurrence.

### 1.2 Board-part consistency check (verify, do not assume)

The abstract reports the GF16 FPGA codec as *"35-of-35 testbench at 323 MHz on
Artix-7 (Xilinx **XC7A35T**)"*. All current hardware work in `trinity-fpga`
targets **XC7A200T** (ALINX AX7203, IDCODE `0x13636093`). Both part numbers occur
in the repository, so **XC7A35T may well be correct for that original measurement**
— this is flagged for the author to confirm, not asserted as an error. If the
323 MHz figure was in fact measured on the AX7203, the abstract names the wrong
device; if it was measured on an XC7A35T board, no change is needed and the two
numbers simply belong to different substrates.

### 1.3 Unaffected claims (checked, no change)

- `e = round((N-1)/phi^2)` rule and the 9/9 reproduction — internal, unchanged.
- "We make no per-rung accuracy or superiority claim" — correct and worth keeping
  verbatim; it is the honesty anchor of the abstract.
- Breadth/toolchain-coherence as an **open conjecture** with FL-002 falsification
  ledger — correct framing, keep.

---

## 2. Paper B — arXiv:2606.09686 (83-format catalog)

*"An 83-Format Numeric Catalog with Bit-Exact Conformance Vectors"*,
submitted 2026-06-08.

### 2.1 The pack count understates the artefact by 13.8x — because the artefact grew after submission

Published abstract:

> ... a catalog of 83 numeric formats spanning 13 families, **a suite of six
> bit-exact conformance packs** covering GF16, MXFP4 element, BF16, FP8 E4M3,
> FP8 E5M2, and E8M0 block scale ...

Live artefact, `t27/conformance/vectors/INDEX_all_formats.json`:

```json
"schema": "t27-conformance-index/v0.1",
"total_formats": 83,
"total_packs":   83,
"bitexact_packs": 75,
"selfconsistent_packs": 0,
"structural_packs": 8
```

83 `*_conformance_v0.json` packs are present in the tree — one per catalogued
format — carrying the schema, SSOT pointer, preprint link and the
`phi^2 + 1/phi^2 = 3` anchor check that the abstract describes.

**Provenance — the paper was accurate when submitted.** Commit history for
`conformance/vectors`:

| date | commit | what |
|---|---|---|
| 2026-06-07 | `00e92fe3` | add v0 vector packs (GF16, FP8 E4M3FN/E5M2, MXFP4 …) — **the original six** |
| *2026-06-08* | — | *paper submitted to arXiv* |
| 2026-06-14 | `16042f46` | **complete catalog-wide pack set for all 83 formats** |
| 2026-06-14 | `f58c298f` | promote 6 structural packs to bit-precise (IBM HFP, …) |
| 2026-06-18 | `3d925d68`, `a7bd4d3e` | `bitexact_selfconsistent` CI gate; promote 6 wide GF rungs |
| 2026-07-05 | `997d5b51`, `38efad6c`, `ea15cd54` | gf128 / gf512+gf1024 / gf256 → strict SW-bitexact |
| 2026-07-29 | `8c20cbd6` | instance packs, structural (q_format / minifloat) |

So "six packs" was **true on 2026-06-08** and became stale six days later. The v2
framing should therefore be *"the pack set was completed after v1"*, not *"v1
undersold"* — the former is what actually happened and is the stronger, more
defensible story.

**Proposed replacement:**

> ... a catalog of 83 numeric formats spanning 13 families, **a catalog-wide
> suite of 83 bit-exact conformance packs — one per format, of which 75 are
> bit-exact and 8 structural** — and an IEEE P3109 cross-walk ...

with a version note in the body:

> v1 (2026-06-08) described the initial six packs, which were the complete set at
> the time of submission. The catalog-wide set of 83 packs was completed on
> 2026-06-14 and strengthened through 2026-07-29; v2 reports the completed set.

This is the single largest improvement available to either paper: the central
contribution is currently reported at **7 % of its actual coverage**.

### 2.2 SHA-256 fingerprint claim — verified TRUE, phrasing could be tightened

The abstract says *"Each pack is a self-contained JSON document with a SHA-256
fingerprint"*. The fingerprints exist — 83 of them — but they live in
`INDEX_all_formats.json`, one entry per pack:

```json
{ "id": "binary16", "file": "binary16_conformance_v0.json", "kind": "bitexact",
  "n_vectors": 8, "source": "generated by gen_all_formats.py",
  "sha256": "84fd7629430b06d761ac3b92fc85208c472a4582040b1ac2001cc87a6612f7b4" }
```

The claim is substantively correct; only the location is imprecise (the digest is
*of* the pack, recorded in the index, rather than *inside* the pack). Optional
tightening: *"each pack carries a SHA-256 fingerprint recorded in a signed index"*.
**No integrity problem here** — recorded so a reviewer's version of this question
is already answered.

### 2.3 ml_dtypes 0.5.4 — VERIFIED CURRENT, do not change

The abstract cross-validates against **ml_dtypes 0.5.4** (Google/JAX). Checked
against PyPI on 2026-07-31: **0.5.4 is the latest release**. This reference is not
stale and must not be "modernised" — changing it would be churn, and would break
the reproducibility of the reported cross-validation.

### 2.4 IEEE P3109 v3.2.0 — REQUIRES VERIFICATION BEFORE SUBMITTING

The abstract cites an *"IEEE P3109 v3.2.0 cross-walk"*. Project notes elsewhere
refer to a **P3109 v4.0** carrying a kappa-approximation in §4.4. That newer
version has **not been verified in this pass** — P3109 drafts are not exposed
through a machine-readable endpoint that was checked here. **Do not edit this
number on the strength of a note.** Before submitting v2, confirm the current
draft version from the P3109 working group directly; if it has moved, the
cross-walk section (not just the version string) needs re-checking, because a
changed draft can change the mapping itself.

---

## 3. Verified-unchanged summary

Items checked in this pass that need **no** edit — recorded so a later pass does
not re-litigate them:

| item | paper | verdict |
|---|---|---|
| ml_dtypes 0.5.4 | B | latest on PyPI 2026-07-31 — keep |
| SHA-256 fingerprints | B | present (83, in the index) — claim holds |
| 83 formats / 13 families | B | matches `total_formats: 83` — keep |
| anchor `phi^2 + 1/phi^2 = 3` | A, B | present in every pack + index — keep |
| "no per-rung superiority claim" | A | correct, load-bearing — keep verbatim |
| FL-002 open-conjecture framing | A | correct — keep |

## 4. Priority order

1. **A §1.1** — fabricated-dies claim. Factual claim about physical artefacts on a
   public preprint; the corrected wording already exists in trinity-papers-ru PR #17.
2. **B §2.1** — 6 → 83 packs. Largest understatement; pure upside; provenance clean.
3. **B §2.4** — P3109 version, *after* independent verification.
4. **A §1.2** — board-part consistency, *after* author confirms which substrate.
5. **B §2.2** — fingerprint phrasing, cosmetic.

Items 1 and 2 are independent and can ship in either order.

## 5. Related work published after v1 (added 2026-07-31, pass 2)

Competitor scan over arXiv (`export.arxiv.org` API, sorted by submission date).
Citation state was checked by fetching `paper1-goldenfloat/main_ru.tex` from the
**default branch** and grepping locally — see the method warning in §5.4.

### 5.1 Not cited, and it matters: arXiv:2607.13898

*"Jack of All Scales: A Versatile FPGA Tensor Block for MXFP Precisions"*,
submitted **2026-07-15** — six weeks after Paper A. Verified absent: paper1 cites
24 arXiv IDs in the 2601–2607 range (`2607.07964`, `2607.08095`, `2607.13511`,
`2607.14618`, `2607.21446`); `2607.13898` is **not** among them.

Why it belongs in v2 — two independent reasons:

**(a) It is the nearest FPGA-side neighbour.** They characterise MXFP dot products
on Altera Agilex-5 across soft logic and DSP fixed/float/tensor modes, then propose
DSP tensor-mode modifications for native MXFP support (preferred design point:
+36 % DSP tile area). Paper A's FPGA claim sits on Xilinx Artix-7 with a
soft-logic implementation. The axes are **complementary, not ranked** — different
vendor, different substrate strategy — and that is exactly how the citation should
read. No superiority claim in either direction.

**(b) It independently corroborates a finding Paper A currently does not state.**
From their abstract:

> the tensor mode … **cannot implement MXFP6 (E3M2) or any MXFP8 precisions,
> forcing designers to fall back to lower-density alternatives**

That is an external, different-vendor result showing hard DSP blocks are a poor
fit for narrow formats. It is the same wall the GF work hit from the other side.

### 5.2 Substantive gap: Paper A never discusses DSP vs soft logic

Grep over `main_ru.tex` for `nodsp` / `DSP48` / `DSP block` / `DSP-блок`:
**0 hits.** The paper reports an FPGA codec result without stating that the
implementation is soft-logic-only or why.

The project's own hardware record is that GF multiply synthesis **requires
`-nodsp`**, because DSP48E1 inference produces a routing failure. That is a
measured engineering constraint, currently invisible in the paper, and
arXiv:2607.13898 provides independent external support for the general claim.

Proposed v2 addition (short subsection, FPGA section): state that the GF codec is
implemented in soft logic with DSP inference disabled, give the routing-failure
reason, and cite 2607.13898 as an independent observation of the same
DSP/narrow-format mismatch on a different FPGA family. Status of the joint claim:
`[measured on our substrate]` + `[externally corroborated, different substrate]` —
**not** a general claim about all DSP architectures.

### 5.3 Lower-priority 2026 neighbours (log only, no action yet)

- `MXAttention` — data-free optimal scaling / pre-norm quantization for MXFP4
  attention (2026-07-27).
- *Stable FP4 Training via Transposition-Invariant Block Quantization* (2026-07-27).

Both are quantization-algorithm papers rather than format-family or FPGA work.
They matter for Paper B's relevance framing, not for its correctness. Revisit only
if the MXFP4 section is rewritten.

### 5.4 Verified NOT gaps, and one method warning

- **Tekum is already cited.** *"Tekum: Balanced Ternary Tapered Precision Real
  Arithmetic"* (2025-11-25) — `main_ru.tex` has 8 mentions and the bibitem
  `hunhold2025tekum`. Recorded here so a later pass does not "fix" a non-problem.
  takum (36 mentions) and posit (52) are likewise well covered.
- **METHOD WARNING — do not use GitHub code search for citation checks.**
  `search/code?q=…+repo:gHashTag/trinity-papers-ru` returned `total_count: 0` for
  `2607.17733` (MXSens), a **known positive** that is demonstrably present in
  PR #17's diff. Code search does not index non-default branches and gave a false
  negative on the control. Every citation claim in §5 was instead verified by
  fetching the file contents from the default branch and grepping locally. Any
  future pass must run the same known-positive control before trusting a search.

## 6. P3109 versions and a citation defect (added 2026-07-31, pass 3)

### 6.1 The two papers cite incompatible P3109 versions

| paper | what it cites | submitted |
|---|---|---|
| A — 2606.05017 | bibitem `p3109_v091`: *"IEEE P3109 Working Group … working draft **v0.9.1**, 2025. Reference implementation: `graphcore-research/gfloat`"* | 2026-06-03 |
| B — 2606.09686 | abstract: *"an IEEE P3109 **v3.2.0** cross-walk"* | 2026-06-08 |

The papers are **five days apart** and cite version numbers that cannot both
describe the same document at the same time; a v0.9.1 → v3.2.0 jump in five days
is not plausible. Either the two numbers refer to different artefacts (e.g. the
WG draft versus a versioned cross-walk table of our own), or one is wrong.

**Action:** reconcile before either v2 ships. This is the kind of discrepancy a
reviewer holding both papers finds immediately, and it costs nothing to fix once
the intended referent is known. Do **not** guess which one is right.

### 6.2 The P3109 draft version is NOT publicly verifiable — stop trying

Checked this pass: there is no `P3109/Public` repository, and no release/tag feed
for the working group. The related public repositories —
`awf/p3109-cpp` (C++ implementation, WG participant), `imandra-ai/ieee-p3109`
(updated 2026-07-27), `rutgers-apl/FLoPS` — expose **no draft-version string**.
`graphcore-research/gfloat` is named by Paper A as the reference implementation
and is the best remaining lead.

This closes the open item from pass 1: the version cannot be confirmed from a
machine-readable public source, so §2.4's instruction stands — the number must
come from the working group directly, not from a note and not from an inference.
Recorded here so pass 4+ does not spend another cycle on it.

### 6.3 Citation defect: `flops2026` has a placeholder author and a paraphrased title

Current bibitem in `main_ru.tex`:

> `\bibitem{flops2026}` **Authors of FLoPS**, *"FLoPS: a Lean~4 formalization of
> IEEE~P3109 low-precision floating-point,"* arXiv:2602.15965, 2026.

Both fields are wrong. Verified against the arXiv API for `2602.15965`:

- **Authors:** Tung-Che Chang, Sehyeok Park, Jay P. Lim, Santosh Nagarakatte
  (Rutgers — the `rutgers-apl/FLoPS` group).
- **Actual title:** *"FLoPS: Semantics, Operations, and Properties of P3109
  Floating-Point Representations in Lean"*.

A paraphrased title is not merely untidy — the reference cannot be found by title
search, which defeats the point of citing it.

**Corrected bibitem:**

```latex
\bibitem{flops2026} T.-C. Chang, S. Park, J. P. Lim, and S. Nagarakatte,
``FLoPS: Semantics, Operations, and Properties of P3109 Floating-Point
Representations in Lean,'' \texttt{arXiv:2602.15965}, 2026.
\url{https://arxiv.org/abs/2602.15965}.
```

**Verified NOT defects** (do not "fix" these): `\bibitem{positstd2022} Posit
Working Group` and `\bibitem{p3109_v091} IEEE P3109 Working Group` are legitimate
corporate authors. A scan of the whole bibliography found `flops2026` to be the
only placeholder-author entry.

### 6.4 Positioning note for Paper B: formal semantics is not implementation conformance

FLoPS is a **Lean 4 machine-checked formalization** of P3109 semantics, from an
active group (`rutgers-apl/FLoPS`, updated 2026-07-28); `imandra-ai/ieee-p3109`
is a second formal-methods effort in the same space. A reviewer of Paper B will
reasonably ask: *if the standard is being formalized in a theorem prover, why do
bit-exact test vectors add anything?*

The answer is short and should be stated explicitly rather than left implicit: a
proof about the specification says nothing about whether a **particular decoder,
kernel or FPGA bitstream** emits the right bits. Formal semantics and executable
conformance vectors sit on different rungs — spec correctness versus
implementation conformance — and they compose rather than compete. Paper B
already cites FLoPS (`flops2026`); it does not yet make this distinction, and it
is the cheapest available strengthening of its contribution framing.

Status of that claim: `[positioning, not a result]` — it asserts complementarity,
not superiority over formal methods.

## 7. The conformance-testing lineage is missing (added 2026-07-31, pass 4)

### 7.1 Competitive scan on Paper B's axis returned nothing — and that is the problem

Targeted arXiv searches, sorted by submission date:

| query | hits |
|---|---|
| `abs:"conformance test vectors" AND abs:"floating-point"` | **0** |
| `abs:"numerical formats" AND abs:reference` | 3 — the top hit is **Paper B itself** |
| `all:"format catalog" AND all:precision` | **0** |

No competing published work was found on Paper B's axis. **This must not be
written up as uniqueness.** It is absence of evidence in one search space, and the
binding no-"first/only/best" rule applies with full force. Vendor test suites,
standards-body vectors and implementation test data exist; they are simply not
published as arXiv papers.

The actionable reading is the opposite of a victory lap: **Paper B has no
established category, so a reviewer has no reference frame for it.** A related-work
section cannot position against peers that do not exist — it has to build the frame
out of adjacent categories. Three of those are already known:

- **implementation test data** — `ml_dtypes` (cited), `graphcore-research/gfloat`;
- **formal formalizations** — FLoPS (Lean 4), `imandra-ai/ieee-p3109`;
- **conformance test suites** — Berkeley TestFloat / SoftFloat (see §7.2).

### 7.2 Paper A does not cite the canonical conformance prior art

> **CORRECTION (pass 5).** This subsection was originally headed *"Neither paper
> cites…"*. That was an overreach: it generalised from `main_ru.tex` (Paper A) to
> both papers without having read Paper B's bibliography. Paper B **does** cite
> IEEE Std 754-2019 (its ref [15]) and **does** cite conformance-testing prior art
> (Wintersteiger, *"Floating-point conformance testing in industrial practice"*,
> IEEE ARITH 2025, ref [11]). The findings below apply to **Paper A only**.
> TestFloat/Hauser remains uncited in both.

Verified over `main_ru.tex` (Paper A, 56 bibitems):

| term | occurrences |
|---|---|
| `TestFloat` | **1** (bare string; no bibitem) |
| `SoftFloat`, `Hauser`, `Berkeley` | **0** |
| a bibitem for **IEEE Std 754 itself** | **none** |

Two omissions, both conspicuous for papers in this area:

**(a) IEEE 754 is discussed in the body but never cited.** A paper proposing a
floating-point family, positioned explicitly against posit, takum, OCP-MX and
P3109, carries 56 references and none of them is the base standard. This is
trivially fixable and is the sort of thing a reviewer notices in the first pass.

**(b) Berkeley TestFloat / SoftFloat (Hauser) is the direct methodological
ancestor and is uncited.** It is *the* established prior art for floating-point
conformance testing. For Paper A this is a related-work hole; for **Paper B it is
the single most likely reviewer objection**, because Paper B's whole contribution
*is* conformance vectors: *"how does this relate to TestFloat?"* is the first
question any referee in this area asks, and the paper currently has no answer on
the page.

The honest answer exists and is strong — TestFloat targets IEEE 754 binary
arithmetic conformance of *operations*; the catalog targets *format decode/encode*
across 83 formats, most of which TestFloat does not cover at all (MXFP, NF4,
posit, takum, LNS, GF). Complementary scopes, different objects under test. It
just needs to be stated.

**Action:** add both citations plus one paragraph in each paper distinguishing
scope. Status: `[related work, no result claimed]`.

### 7.2a RESOLVED, and the finding is stronger: TestFloat-3 is a load-bearing instrument

The pass-4 caveat above (context not read) is now closed. `main_ru.tex` line 1728
sits inside the **pre-registration** block (`Дата предрегистрации: 2026-05-31`) —
i.e. the FL-002 falsification path the abstract promises. Its *Материалы*
paragraph reads:

- RTL GF16: corrected `gf16_mul.v` / `gf16_add.v` from `gHashTag/tt-trinity-gamma` PR #110
- RTL posit16: **PERCIVAL** (Mallasen et al., 2022, arXiv:2111.15286) — cited ✓
- driver: Rust `cli/dlc10` (`gHashTag/t27`)
- toolchain: **OpenXC7 (yosys + nextpnr-xilinx)** or Vivado 2023.2
- **correctness gate: an exhaustive TestFloat-3 run, 0 errors required over
  1 M random samples**, before any area/timing result is accepted

So TestFloat-3 is not mentioned in passing — it is the **correctness gate of the
pre-registered experiment**. That reclassifies the omission: this is an **uncited
tool dependency inside the falsification protocol**, which is a stricter failure
than a related-work gap. A protocol that gates its acceptance criterion on a tool
must cite that tool.

**Two things worth recording as strengths, not defects** (this package should not
only hunt faults):

1. The pre-registration is well formed — explicit thresholds (>15 % area, <85 % of
   posit16 `F_max`), an explicit commitment to report negative results prominently,
   no post-hoc threshold adjustment, and a date. That is a stronger design than
   most format papers carry.
2. The posit16 comparator (PERCIVAL) **is** properly cited.

**Practical blocker worth flagging to the author:** the pre-registered experiment
requires `nextpnr-xilinx` (OpenXC7). That toolchain is *not installed* on the
current workstation — the same gap that blocked the AX7203 P&R task this week. The
falsification experiment cannot run until either OpenXC7 or Vivado 2023.2 is
available. This is a scheduling fact, not a criticism of the paper.

### 7.3 Paper B's full text was not scanned this pass

`paper2-catalog/` holds `ARXIV_UPLOAD_EN_v2.md` (4 kB — arXiv upload metadata
only) and the actual manuscript as `statya2_ru.docx` / `.pdf`. The `.docx` is
binary and was not extracted, so **Paper B's bibliography has not been checked for
`flops2026`-class defects** (§6.3). That check is still open and needs the docx
unpacked locally.

## 8. Paper B bibliography audit — 4 of 20 references are defective (pass 5)

Paper B's manuscript (`paper2-catalog/statya2_ru.docx`) was unpacked and its
20-entry reference list extracted. Every arXiv ID was checked against the arXiv
API. **Four entries (20 %) do not match the work they point at.**

### 8.1 Ref [3] — wholly misattributed (most serious)

| | |
|---|---|
| **paper says** | C. Park, J.-H. Lim, S. Nagarakatte, *"ProofWright: Towards verified floating-point arithmetic"*, arXiv:2511.12294v2, 2025 |
| **arXiv:2511.12294 actually is** | *"ProofWright: Towards **Agentic Formal Verification of CUDA**"* — Bodhisatwa Chatterjee, Drew Zagieboylo, Sana Damani, Siva Hari, Christos Kozyrakis |

**All three listed authors are wrong** (none of Park, Lim or Nagarakatte is on the
paper), **the title is wrong**, and **the subject is wrong** — it is about agentic
formal verification of CUDA, not floating-point arithmetic. This is not a
formatting slip; the citation describes a different work than the ID resolves to.

This is the highest-risk item in this whole package after §1.1. A referee who
follows one link finds it immediately, and a misattributed citation reads as
*references that were generated rather than read* — which would cast doubt on the
rest of the bibliography by association, including the parts that are correct.

**Action:** decide what was actually meant. If the intended reference was the
Rutgers group's work, ProofWright is the wrong ID; if arXiv:2511.12294 was
intended, the authors and title must be replaced with the real ones. Do not patch
half of it.

### 8.2 Refs [19] and [20] — no authors, paraphrased titles

| ref | paper says | reality (arXiv API) |
|---|---|---|
| [19] | *"Formal models of Tensor Core numerics for reproducible GEMM"*, arXiv:2512.07004 — **no authors** | *"Accurate Models of NVIDIA Tensor Cores"* — Faizan A. Khattak, Mantas Mikaitis |
| [20] | *"TAO: Tolerance-aware verification of numerical operators"*, arXiv:2510.16028 — **no authors** | *"TAO: Tolerance-Aware **Optimistic** Verification for **Floating-Point Neural Networks**"* — J. Yao, H. Su, T. Liao, Z. Cheng, H. Zhang, X. Wang, P. Viswanath |

Both entries omit the author list entirely and paraphrase the title. As in §6.3, a
paraphrased title cannot be found by title search.

### 8.3 Ref [4] — same defect class as Paper A's `flops2026`

| | |
|---|---|
| **paper says** | C. Chang, C. Park, J.-H. Lim, S. Nagarakatte, *"P3109 FLoPS: A Lean 4 formalization of IEEE P3109 floating-point semantics"* |
| **reality** | Tung-Che Chang, Sehyeok Park, Jay P Lim, Santosh Nagarakatte, *"FLoPS: Semantics, Operations, and Properties of P3109 Floating-Point Representations in Lean"* |

Three of four initials are wrong (`C. Chang` → `T.-C. Chang`; `C. Park` →
`S. Park`; `J.-H. Lim` → `J. P. Lim`; only Nagarakatte is right) and the title is
paraphrased. **The same work is mis-cited in both papers** (Paper A's `flops2026`,
§6.3) — so this is a systematic issue with one source, not two independent slips.

### 8.4 Corrected entries

```
[3]  B. Chatterjee, D. Zagieboylo, S. Damani, S. Hari, C. Kozyrakis,
     "ProofWright: Towards Agentic Formal Verification of CUDA,"
     arXiv:2511.12294, 2025.            [ONLY IF this ID was the intended source]

[4]  T.-C. Chang, S. Park, J. P. Lim, S. Nagarakatte, "FLoPS: Semantics,
     Operations, and Properties of P3109 Floating-Point Representations in Lean,"
     arXiv:2602.15965, 2026.

[19] F. A. Khattak, M. Mikaitis, "Accurate Models of NVIDIA Tensor Cores,"
     arXiv:2512.07004, 2025.

[20] J. Yao, H. Su, T. Liao, Z. Cheng, H. Zhang, X. Wang, P. Viswanath,
     "TAO: Tolerance-Aware Optimistic Verification for Floating-Point Neural
     Networks," arXiv:2510.16028, 2025.
```

### 8.5 Verified correct — do not touch

Checked and matching: [1] self-citation 2606.05017, [2] Hunhold takum 2412.20273,
[5] Rouhani MX 2310.10537, [15] **IEEE Std 754-2019** (so Paper A's omission,
§7.2, is Paper A's alone), [16] OCP MX v1.0, [17] ml_dtypes 0.5.4 (matches PyPI,
§2.3), [18] **IEEE SA P3109 Interim Report v3.2.0**.

### 8.6 The P3109 "version conflict" of pass 3 is RESOLVED — no error

Ref [18] reads *"IEEE SA P3109 **Interim Report** v3.2.0"*; Paper A's
`p3109_v091` reads *"working **draft** v0.9.1, 2025"*. These are **two different
documents in two different series**, not two versions of one document. §6.1's
hedge — *"either they name different artefacts or one is wrong"* — resolves to
**different artefacts**. No edit is required, and pass 6+ should not reopen it.

## 9. What this package cannot do

Replacing an arXiv entry requires the submitting author's arXiv account. This
document prepares the exact old → new text and the evidence for each edit; the
submission itself is the author's action. The repository carries an
`arxiv-replace-pipeline` skill that covers that workflow.

Nothing in `gHashTag/t27` or `gHashTag/trinity-papers-ru` was modified by this
pass — it was read-only apart from this file.
