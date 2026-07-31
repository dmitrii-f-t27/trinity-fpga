# Verification dossier — what 41 passes established, against what the papers say

> Produced 2026-07-31. Companion to `ARXIV_V2_CORRECTION_PACKAGE.md` (what to fix)
> and `ARXIV_ABSTRACTS_READY_TO_PASTE.md` (the text to paste). This one answers a
> different question: **what can the papers now honestly claim that they don't?**
>
> Every row cites the spec under `specs/numeric/` holding the measurement. Nothing
> here is asserted from memory.

---

## 1. Claims the papers make, now independently verified

These strengthen the papers at zero cost: the claim already exists in the text, and
there is now an executable check behind it.

| paper claim | verification | evidence |
|---|---|---|
| `e = round((N-1)/φ²)` generates the family | **17/17** catalogued widths satisfy it, recomputed at 60-digit precision against the oracle's own parameters | `phi_rule_verification.t27` |
| Lucas-exact accumulator at 500 digits, n = 1…256 | **256/256**, worst residue at the representation floor (relative 1e-499 against magnitude 1e107) | `lucas_exact_verification.t27` |
| packs cross-validated against ml_dtypes 0.5.4 | **66,224 codes, 0 divergences** — and *exhaustive*, not sampled, on every format both sides implement | `ml_dtypes_crossval.t27` |
| each pack carries a SHA-256 fingerprint | **83 present**, in `INDEX_all_formats.json`, one per pack | correction package §2.2 |
| "no per-rung superiority claim" (Paper A) | holds throughout; nothing measured here contradicts it | — |

## 2. Verified, and NOT in either paper — the under-claimed set

Each of these is a real property of the artefact, established by measurement, that
a reader of the papers cannot learn.

| what is true | why it is worth saying | evidence |
|---|---|---|
| **83 conformance packs**, not six — 75 bit-exact + 8 structural | the abstract reports the central contribution at **7 %** of its coverage; the paper's own body already says 49/34 | correction package §2.1, §12 |
| the **8 empty packs are exactly the 8 declared structural** | the corpus is self-consistent where a sceptic would expect concealment | `corpus_wide_pack_audit.t27` |
| wide formats serialise values as **decimal strings** with an explicit `value_encoding` | a working answer to *"how do you publish bit-exact vectors for formats wider than a double?"* — gf1024 has a 632-bit mantissa | `layout_b_audit.t27` |
| the oracle layer has **three distinct exactness techniques** — rational, log-domain, algebraic ring ℚ[φ] | most catalogues have one; the ℚ[φ] ring rests on the papers' own anchor `φ² = φ + 1` | `oracle_fidelity_map.t27` |
| **12 oracles verified exact** — 19,106 codes, zero float returns, zero inadmissible denominators | "bit-exact" is usually asserted; here it is measured | `oracle_fidelity_map.t27` §pass 39 |
| **commutativity holds everywhere** add and mul are exposed — 13 families, 576 ordered pairs each, 0 violations | the one arithmetic law admitting no design-choice defence | `arithmetic_invariant_sweep.t27` |
| `double_double` / `quad_double` hold the **non-overlap invariant** | the defining property of an error-free expansion, and the only evidence these two formats have | `oracle_fidelity_map.t27` §pass 40 |
| the LNS oracle **returns `special:irrational` rather than rounding silently** | it declines to claim exactness it does not have — a discipline worth naming | `intrinsic_invariant_sweep.t27` |
| the HW conformance golden is an **exact logarithmic takum** — 60,485/60,485 | independent mpmath implementation, verified against the format author's own library | `takum_variant_split.t27` |

## 3. Claims still unverified — and why

Stated so no reader mistakes silence for confirmation.

| claim | blocker | who can move it |
|---|---|---|
| GF16 FPGA codec, 35/35 at 323 MHz | `nextpnr-xilinx` absent; the same gap blocks post-route P&R and the paper's own FL-002 experiment | anyone with openXC7 or Vivado |
| the `(9/9)` reproduction count | off in **both** directions; needs to know which widths predate the rule | author (`WIDTH_PROVENANCE`) |
| "83 formats spanning **13 families**" | never checked; a module grouping gives 15, which would not be a defect | author (`FAMILY_TAXONOMY`) |
| the accumulator **path** (as distinct from the identity) | the identity verifies; the implementation was never executed | author (`ACCUMULATOR_IMPLEMENTATION`) |
| IEEE P3109 draft version | **not publicly verifiable** — no `P3109/Public`, no release feed | the working group |
| GF commutativity above gf48 | exact-rational sweeps at gf64+ do not terminate; timing a single gf64 multiply exceeded two minutes | a different verification strategy |
| takum32/64 published-pack variant | the ctypes binding returned NaN for every code; measurement void | rebuild via the C bridge |

## 4. What the papers say that measurement contradicts

Only two, both already in the correction package, both cheap.

| where | the problem |
|---|---|
| Paper A abstract | *"the fabricated TTSKY26b dies"* — asserts fabricated dies exist; the silicon track was cancelled. Present in **v3**, having survived two revisions |
| Paper B references | **8 of 20** carry a wrong title, wrong authors, or both — including the companion-paper self-citation, and a takum reference whose title belongs to neither work |

## 5. The honest summary

**The science holds.** Every central technical claim checkable without hardware was
recomputed independently and passed. The defects are in citations and in unstated
distinctions — not in the results.

**The papers undersell the artefact more than they oversell it.** One abstract
sentence overstates (fabricated dies); a whole section of genuine, measured
properties goes unmentioned — the pack count above all, at 7 % of true coverage.

**Eleven times in 41 passes, an alarming measurement turned out to be my own
harness.** Every count in §§1–3 survived that filter; the retracted ones are
recorded as retracted rather than deleted. That is the reason to trust the
remaining numbers, and it is also the reason each row here names its spec.
