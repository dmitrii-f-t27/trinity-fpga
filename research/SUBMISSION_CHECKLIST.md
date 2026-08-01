# arXiv replacement — what to change, in order

> One page. Everything here is verified against the **currently published** text
> (Paper A v3, Paper B v2, both updated 2026-06-22, re-fetched 2026-08-01).
> Re-read end to end on 2026-08-01 (pass 71) against everything learned since it was
> written; §4 had gone stale enough to contradict §2, and did.
>
> Evidence for every line is in `VERIFICATION_DOSSIER.md`; the verbatim replacement
> text is in `ARXIV_ABSTRACTS_READY_TO_PASTE.md`, `ARXIV_BODY_FIXES_READY_TO_PASTE.md`
> and `RELATED_WORK_READY_TO_PASTE.md`. Nothing below needs those files to be read
> first — they are where to look if a line is disputed.

---

## 0. Read this first — which document are you editing?

There are **three** GoldenFloat papers, with three different bibliographies, and the
fixes below do not apply to all of them equally:

| document | references | last touched |
|---|---|---|
| `goldenfloat-preprint/gf_preprint_v19.tex` | **28** | 2026-06-07 |
| **arXiv:2606.05017v3 — what a reader sees** | **33** | 2026-06-22 |
| `trinity-papers-ru/paper1-goldenfloat/main_ru.tex` — Russian, for ВАК journals | **56** | 2026-08-01 |

Two things follow:

- **`goldenfloat-preprint` is not the source of v3 — this is now proven.** Five
  references appear in the published v3 and nowhere in `gf_preprint_v19.tex`, two of
  them postdating that repository's last commit (2026-06-07): an NVIDIA forum post
  dated 2026-06-17, and **Paper B itself**, which appeared 2026-06-08.
  **Editing that file and submitting it would delete Paper A's citation of Paper B.**
  Locate the tree that actually produced v3 before touching anything.
- **`ARXIV_BODY_FIXES_READY_TO_PASTE.md`'s line numbers point into `main_ru.tex`** —
  the Russian ВАК submission, not the preprint. The *claims* hold against the
  published text (re-verified: IEEE 754 and TestFloat are uncited in v3's 33
  references). The *locations* do not.

§1 below is stated against the **published arXiv text**. Use the line numbers only
when editing the Russian manuscript.

---

## 1. Do these — high value, low cost, no new work required

| # | paper | change | why | cost |
|---|---|---|---|---|
| **1** | **B, abstract** | "a suite of **six** bit-exact conformance packs" → **83 packs (75 bit-exact, 8 structural)** | The single largest defect in either paper, and it is an *under*-claim. The abstract reports the central contribution at ~7 % of its actual coverage. The body already says 49/34. | one sentence |
| **2** | **A, abstract** | delete or rewrite "**the fabricated TTSKY26b dies** carry the defective multiplier portfolio" | The only claim in either paper that measurement contradicts — the silicon track was cancelled, so there are no fabricated dies to carry anything. Present in v1, v2 and v3. | one clause |
| **3** | **B, references** | fix **at least 11 of 20** bibitems | Resolved mechanically against arXiv and Crossref, not by reading: **9 of the 12** entries carrying an arXiv id differ from the work that id resolves to. Four are outright misattributions — **[2]**, **[3]** (*"ProofWright: Towards verified floating-point arithmetic"* is really *"…Agentic Formal Verification of CUDA"*), **[8]**, **[13]**. **[1]** is the companion-paper self-citation under a title Paper A does not have. **[19]** and **[20]** carry no title at all. Outside that set, **[12]** credits *"C. Hunhold"* for libtakum — the author is **Laslo** Hunhold — and **[18]** attaches *"v3.2.0"* to the Interim Report, which carries no version number. | verbatim replacements supplied |
| **3a** | **both** | work from **`BIBLIOGRAPHY_FIXES.md`** | One table, both papers, **20 entries**: 8 in A and 12 in B, each with what it currently says, what the identifier actually resolves to, and the defect class. Regenerated from the live arXiv API rather than transcribed. Paste-ready LaTeX for all of them is in `CORRECTED_BIBITEMS.tex`. | — |
| **3b** | **A, references** | fix ref **[11]**, and add the work it was meant to cite | Cited as *"L. Hunhold, Hardware evaluation of takum arithmetic, ARITH 2025, DOI 10.1109/ARITH64983.2025.00019"*. That DOI resolves — checked against Crossref — to **"Evaluation of Bfloat16, Posit, and Takum Arithmetics in Sparse Linear Solvers", Hunhold and Quinlan**: wrong title, wrong author list, wrong subject. It is also a **duplicate of ref [10]**, which cites the same work as `arXiv:2412.20268`. So the bibliography carries one paper twice under two titles, and the ARITH hardware-evaluation paper is missing entirely. | one entry replaced, one added |
| **4** | **B, abstract** | say what the P3109 cross-walk maps — **layout**, not values | The abstract says it "maps each pack to its **corresponding** standards-track configured format". The working group's own Interim Report, §3.1, is normative: *"For signed formats, the exponent bias **shall be** B = 2^(K−P−1). For unsigned formats, the exponent bias **shall be** B = 2^(K−P)"*, and Annex A.5 states plainly *"This differs from IEEE-754"*. So every `binaryKpP` value is exactly **twice** its same-layout IEEE/OCP counterpart. Confirmed empirically at **all 252 configurations** of their published tables and across **258,524 finite codes** against four packs — one distinct ratio. The special-value codes differ too, by exactly the count P3109's *"single NaN, no negative zero"* predicts: 3, 9 and 2049 observed, 3, 9 and 2049 predicted. Mapping layout is worth publishing; the sentence needs one word to say so. | one word |
| **5** | **B, related work** | add the four-paragraph subsection | Positions the corpus against *published vector sets*, measured from six projects — including the P3109 working group, which ships **504 exhaustive CSV tables (154 MB)** and whose README forbids using them for conformance. That is the real gap this work fills. | one subsection |

**Items 1–4 are corrections. Item 5 is an addition** — skip it if the replacement
needs to be minimal.

## 2. Answer these, or the numbers stay unverifiable

Nobody outside the project can settle these. Each has a spec holding the question.

| question | what is unclear | spec |
|---|---|---|
| the `(9/9)` reproduction count | Off in **both** directions. 17/17 catalogued widths satisfy `e = round((N−1)/φ²)`; the abstract claims 9. Which nine are the *realised* widths, and which postdate the rule? | `WIDTH_PROVENANCE` |
| "83 formats spanning **13 families**" | Never checkable from outside. A module grouping gives 15 — which would not be a defect, just a different cut. | `FAMILY_TAXONOMY` |
| the accumulator **path** | The Lucas identity verifies at 500 digits, n = 1…256. The *implementation* has never been executed here. | `ACCUMULATOR_IMPLEMENTATION` |
| ~~IEEE P3109 **v3.2.0**~~ **— settled, moved to §1 item 3** | Paper B ref [18] names the artefact outright: *"IEEE SA P3109 Interim Report v3.2.0"*. That is the same Interim Report Paper A's [27] points at, and it carries **no version number anywhere in its text**. So this was never "two different document series" — it is a version string attached to a document that has none, in both papers, differently. **Cite the Interim Report by retrieval date.** | — |

## 3. Blocked on a toolchain, not on you

- **GF16 FPGA codec, 35/35 at 323 MHz** — `nextpnr-xilinx` is absent here. The same
  gap blocks post-route P&R and the paper's own FL-002 experiment. Anyone with
  openXC7 or Vivado can settle it in an afternoon.
- **XC7A35T** in Paper A's abstract — worth double-checking against the board the
  measurement was actually taken on.

## 4. Deliberately NOT flagged

Checked and found correct, listed so nobody re-opens them:

- The **83 vs 84** count. The v2 replacement corrected **both the title and the
  abstract**; `ERRATA_2026-06-14.md` is complete and honest. Nothing left to do.
- **ml_dtypes 0.5.4** — the version string is correct and the cross-validation
  reproduces against it exactly (66,224 codes, 0 divergences).
  *(P3109's version was listed here as fine until pass 69 established it is not —
  see §2. Left visible rather than deleted, because a checklist that quietly moves
  an item from "settled" to "open" is harder to trust than one that says it did.)*
- Paper A's **related-work positioning** — it already names posit, takum, OCP-MX and
  IEEE P3109 explicitly. An earlier draft of this package implied otherwise; that
  was wrong and is corrected.
- The **`φ² + 1/φ² = 3`** anchor, the **SHA-256** fingerprints, the **ml_dtypes**
  cross-validation, the **no-superiority-claim** discipline — all verified, all
  hold.

## 5. What the papers could claim and don't

Measured, in the repository, and mentioned in neither paper. All of §2 of the
dossier, but the three that would most change a reader's impression:

- **The corpus uses three distinct exactness techniques** — exact rational,
  log-domain, and an algebraic ring ℚ[φ] that closes via the papers' own anchor
  `φ² = φ + 1`. Most catalogues have one.
- **Wide formats serialise as `A·2^B` dyadic strings** with an explicit
  `value_encoding` field. This is a working answer to "how do you publish bit-exact
  vectors for formats wider than a double?" — `gf1024` has a 632-bit mantissa — and
  no document anywhere says the corpus does it.
- **Commutativity holds everywhere add and mul are exposed**, now including every
  GoldenFloat rung through gf1024 — 8,865 ordered pairs, zero violations.

---

## 6. The artefact itself has been repaired

The papers point a reader at `github.com/gHashTag/t27`. Five defects that a reader
following that pointer would have hit are fixed and merged (#1576, #1578, #1582,
#1584, #1589):

- the pack generator **could not run on a clean checkout** — its catalog came from an
  uncommitted `/tmp` path, so the corpus could be read but not regenerated;
- re-running that generator **silently reverted** the 2026-07-05 promotions,
  rewriting the index from 75/0/8 back to 69/6/8;
- the **six witness decode references failed standalone**, defaulting to a path under
  `/home/user/workspace` — these are the files honesty rule #10 points a sceptic at,
  and running one is the first thing an auditor does;
- CI demanded an erratum the v2 replacement had already made, on every run;
- `cocotb_ref_model.py` **could not be imported at all**.

Regeneration now reproduces the committed corpus exactly — 83/83 digests unchanged —
and a new gate locks the index against the packs it summarises.

---

### One caution about this checklist

Roughly fifteen alarming measurements across seventy passes turned out to be defects
in my own harness rather than in the artefact, and were withdrawn before publication:
a defaulted format width that manufactured 57,330 phantom defects, an oracle loader
that silently skipped two formats, API throttling read as dead references, a URL
typo that made 238 files look unreadable. One correction was *not* caught in time — a
"fix" to `takum_ref.py` shipped as a PR and was retracted unmerged once the module's
docstring turned out to document the behaviour as deliberate.

So treat §1 as claims with evidence attached, not as instructions. Every line names
where to check it. **The science holds** — the defects are in citations and in things
left unsaid, not in the results.
