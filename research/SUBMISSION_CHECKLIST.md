# arXiv replacement — what to change, in order

> One page. Everything here is verified against the **currently published** text
> (Paper A v3, Paper B v2, both updated 2026-06-22, re-fetched 2026-08-01).
>
> Evidence for every line is in `VERIFICATION_DOSSIER.md`; the verbatim replacement
> text is in `ARXIV_ABSTRACTS_READY_TO_PASTE.md`, `ARXIV_BODY_FIXES_READY_TO_PASTE.md`
> and `RELATED_WORK_READY_TO_PASTE.md`. Nothing below needs those files to be read
> first — they are where to look if a line is disputed.

---

## 1. Do these — high value, low cost, no new work required

| # | paper | change | why | cost |
|---|---|---|---|---|
| **1** | **B, abstract** | "a suite of **six** bit-exact conformance packs" → **83 packs (75 bit-exact, 8 structural)** | The single largest defect in either paper, and it is an *under*-claim. The abstract reports the central contribution at ~7 % of its actual coverage. The body already says 49/34. | one sentence |
| **2** | **A, abstract** | delete or rewrite "**the fabricated TTSKY26b dies** carry the defective multiplier portfolio" | The only claim in either paper that measurement contradicts — the silicon track was cancelled, so there are no fabricated dies to carry anything. Present in v1, v2 and v3. | one clause |
| **3** | **B, references** | fix **8 of 20** bibitems | Wrong titles, wrong authors, or both — including the companion-paper self-citation **[1]/[2]** and ref **[3]**, which is wholly misattributed (wrong authors, wrong title, wrong subject). One clicked link damages the whole bibliography. | verbatim replacements supplied |
| **4** | **B, abstract** | say what the P3109 cross-walk maps — **layout**, not values | The abstract says it "maps each pack to its **corresponding** standards-track configured format". The working group's own Interim Report, §3.1, is normative: *"For signed formats, the exponent bias **shall be** B = 2^(K−P−1). For unsigned formats, the exponent bias **shall be** B = 2^(K−P)"*, and Annex A.5 states plainly *"This differs from IEEE-754"*. So every `binaryKpP` value is exactly **twice** its same-layout IEEE/OCP counterpart. Confirmed empirically at **all 252 configurations** of their published tables and across **258,524 finite codes** against four packs — one distinct ratio. Mapping layout is worth publishing; the sentence needs one word to say so. | one word |
| **5** | **B, related work** | add the four-paragraph subsection | Positions the corpus against *published vector sets*, measured from six projects — including the P3109 working group, which ships **504 exhaustive CSV tables (154 MB)** and whose README forbids using them for conformance. That is the real gap this work fills. | one subsection |

**Items 1–3 are corrections. Item 4 is an addition** — skip it if the replacement
needs to be minimal.

## 2. Answer these, or the numbers stay unverifiable

Nobody outside the project can settle these. Each has a spec holding the question.

| question | what is unclear | spec |
|---|---|---|
| the `(9/9)` reproduction count | Off in **both** directions. 17/17 catalogued widths satisfy `e = round((N−1)/φ²)`; the abstract claims 9. Which nine are the *realised* widths, and which postdate the rule? | `WIDTH_PROVENANCE` |
| "83 formats spanning **13 families**" | Never checkable from outside. A module grouping gives 15 — which would not be a defect, just a different cut. | `FAMILY_TAXONOMY` |
| the accumulator **path** | The Lucas identity verifies at 500 digits, n = 1…256. The *implementation* has never been executed here. | `ACCUMULATOR_IMPLEMENTATION` |
| IEEE P3109 **v3.2.0** | The repo **is** public — `github.com/P3109/Public`, updated 2026-07-29 — and its *IEEE P3109 Interim Report.pdf* carries **no version number anywhere in its text**, only "unapproved IEEE Standards Draft, subject to change" and a 2026 copyright. So neither v3.2.0 nor Paper A's v0.9.1 can be checked against the published document, and **the companion papers cite different versions of the same draft**. Cite the Interim Report by retrieval date instead. | author |

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
- **P3109 v3.2.0**, **ml_dtypes 0.5.4** — version strings are internally consistent.
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

### One caution about this checklist

Fourteen alarming measurements in 61 passes turned out to be defects in my own
harness, not in the artefact, and were withdrawn before publication. One correction
was *not* caught in time — a "fix" to `takum_ref.py` shipped as a PR and was
retracted unmerged once the module's docstring turned out to document the behaviour
as deliberate.

So treat §1 as claims with evidence attached, not as instructions. Every line names
where to check it. **The science holds** — the defects are in citations and in
things left unsaid, not in the results.
