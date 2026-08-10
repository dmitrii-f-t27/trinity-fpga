# A third family breaks the 4-bit result — and with it the fitted λ

**Status: "φ wins at four bits" is withdrawn as a law. It is a two-model outcome, not a
three-model one. The 3- and 5-bit results survive on all three families.**

## The test

λ was fitted to make φ win at 4 bits on SmolLM2 and Qwen. Six bits held on both but did not
exercise λ — at that budget nothing is flushed and the second term is negligible. The only test
that exercises λ is a **new family at the crossover budget**.

**Pythia-160m**: GPT-NeoX rather than Llama, the Pile rather than FineWeb/Qwen data, its own
tokenizer, fused `query_key_value` attention. Nothing about it entered the fit. Its output head is
`embed_out`, not `lm_head` — filtering only on `lm_head` would have quantised the head and
silently changed what was being compared.

Predictions were printed before measuring.

## Result

| bits | measured ladder perplexities | winner | MSE-only | count (λ=0.01) | energy (λ=0.79) |
|---|---|---|---|---|---|
| 3 | shift 3 354, phi 120 750, supergold 3.8e6, plastic 2.5e7 | shift | ✅ | ✅ | ✅ |
| **4** | **supergold 52.12**, phi 55.18, shift 105.67, plastic 145.32 | **supergold** | ✅ | ❌ | ❌ |
| 5 | plastic 33.20, supergold 39.91, phi 52.12, shift 104.94 | plastic | ✅ | ✅ | ✅ |

**Two failures at once.**

1. **φ does not win at 4 bits on Pythia — supergolden does.** The 4-bit winner is
   **model-dependent**: φ, φ, supergolden across the three families. The replication that
   "separated the law from coincidence" was two models; the third breaks it.

2. **The two-term criterion fails at exactly the budget it was invented to fix.** Both λ variants
   predict φ; the measurement says supergolden. λ was fitted to force φ at 4 bits on two models,
   so on a model where φ does not win, λ makes the prediction worse than no λ at all.

**The single-term closed form is correct on all three Pythia budgets** — it predicted supergolden
at 4 bits, which is what happened.

## Scorecard over all three families

| criterion | SmolLM2 | Qwen | Pythia | total |
|---|---|---|---|---|
| MSE-only (the original closed form) | 2/3 | 2/3 | **3/3** | **7/9** |
| two-term, count | 3/3 | 3/3 | 2/3 | 8/9 |
| two-term, energy | 3/3 | 3/3 | 2/3 | 8/9 |

The two-term score is still ahead on raw count, but it is ahead **only on the two models it was
fitted to**, and it loses on the one it was not. That is the signature of overfitting, and with
one free parameter against six binary outcomes it is exactly what should have been suspected.

## What actually survives across three families

    3 bits   shift    on SmolLM2, Qwen, Pythia    robust
    4 bits   phi / phi / supergolden              MODEL-DEPENDENT
    5 bits   plastic  on SmolLM2, Qwen, Pythia    robust

**The hierarchy result is real at 3 and 5 bits**: coarse budgets want powers of two, fine budgets
want the plastic number, on three unrelated architectures. That is the part worth keeping, and it
is now better supported than before — three families, not two.

**Four bits is the crossover, and at a crossover the winner is decided by the specific
distribution, not by the budget.** That is consistent with everything measured: it is the budget
where reach and resolution are comparable, and Pythia's weights sit on the other side of the
boundary from SmolLM2's and Qwen's.

## What this costs and what it buys

Withdrawn:
- "the law reproduced completely on the second model" — it reproduced on two of three, and the
  4-bit row does not reproduce at all;
- "φ at 4 bits, in the worst case a draw and ahead on the larger model" — ahead on two families,
  **behind on a third**;
- the two-term criterion as a law. It remains a description of two models.

Kept, and strengthened:
- 3- and 5-bit winners, now on three families;
- the three-regime picture (flush-dominated / crossover / resolution-dominated), which *predicts*
  that the 4-bit winner should be the fragile one — and it is;
- the single-term closed form, which is the only criterion that has never been wrong on a family
  it was not fitted to.

## The next honest step

Not another λ. The 4-bit winner should be predicted from where a model's weights sit relative to
the crossover, which is a continuous quantity, not a constant to tune. Pythia's weight kurtosis
and flush fractions at 4 bits are already measured; the question is whether they place it on the
supergolden side of a boundary that also places SmolLM2 and Qwen on the φ side. If one boundary
separates all three, that is a law with no fitted parameter. If it does not, the 4-bit budget
should simply be reported as measured per model.

---

# Follow-up: no parameter-free boundary, and the cost table rebuilt on what survived

## A — is there a boundary that separates the 4-bit winners?

`boundary.py`. Five parameter-free quantities, computed from each model's own weights, asked to
put Pythia (supergolden) on one side and SmolLM2/Qwen (φ) on the other:

| quantity | SmolLM2 | Qwen | Pythia | separates? |
|---|---|---|---|---|
| excess kurtosis of \|w\|/rowmax | 0.4171 | 0.7698 | 0.3832 | **yes**, boundary in (0.383, 0.417) |
| `r*` of the single-term form at 4 bits | 1.455 | 1.486 | 1.463 | no |
| relative MSE gap, (φ − sg)/sg | 0.2833 | 0.1896 | **0.2719** | no |
| flush-fraction gap, φ − sg | −0.0698 | −0.0825 | −0.0699 | no |
| fraction of weights below 0.1 | 0.3025 | 0.3537 | 0.3040 | no |

**Only kurtosis separates, and by 3.4 %** — Pythia at 0.383 against SmolLM2 at 0.417, with Qwen
far away at 0.770. With three points and five candidates, one separation at that margin is what
chance produces. It is not a law.

**The informative row is `gap`.** The relative MSE distance between φ and supergolden is
0.2833 / 0.1896 / 0.2719 — and **Pythia sits between the two models that disagree with it**. The
weight statistics of the three families are nearly identical at 4 bits; the perplexity outcome is
not. So no weight statistic is likely to predict the 4-bit winner, because the weight statistics
do not distinguish the cases.

The measured margins say the same thing: φ ahead by 2.7 % on SmolLM2 and 10.7 % on Qwen,
supergolden ahead by 5.9 % on Pythia. **Four bits is a near-tie whose direction flips.**

**Conclusion: the 4-bit budget should be reported as measured per model, not predicted.**

## C — the cost table, rebuilt around what replicates

`cost_surviving.py`. A ratio that is a root of a monic integer polynomial makes multiplication a
shift-and-add recurrence; the adder count is the number of non-zero coefficients minus one.

The first version of this table **guessed two of the polynomials and both were wrong** — plastic
had its coefficients reversed, and the degree-4 ratio was given `r⁴ = r³ + 1`, which has no root
at 1.1787. A numerical root check caught both. The minimal polynomials, found by search:

| ladder | recurrence | degree | adders | root check | LUT | reg | Fmax |
|---|---|---|---|---|---|---|---|
| shift | r = 2 | 1 | **0** | 0 | — | — | — |
| phi | r² = 1 + r | 2 | 1 | 0 | 223 | 192 | 247.10 |
| supergold | r³ = 1 + r² | 3 | 1 | 4e-16 | — | — | — |
| plastic | r³ = 1 + r | 3 | 1 | 0 | 228 | 200 | 231.21 |
| deg-4 | r⁴ = 1 + r + r² − r³ | 4 | **3** | 8e-10 | 469 | 320 | 184.98 |

The derived adder count for degree 4 is **3**, which matches the independently measured value in
the earlier synthesis run — a check that the method is sound rather than a restatement of it.

### What the surviving results actually require

    3 bits -> shift     degree 1, ZERO adders
    5 bits -> plastic   degree 3, ONE adder
    4 bits -> model-dependent (phi or supergolden), both ONE adder

**φ is not required by anything that replicated.** It appears only in the 4-bit case, which is
model-dependent, and where supergolden costs the same single adder. A node implementing **a bare
shifter plus one degree-3 recurrence** covers every budget whose winner holds across three
families. The degree-2 rung buys nothing robust.

Price of the surviving rung, from the measured synthesis: plastic against φ is **1.022× LUT,
1.042× registers, 0.936× Fmax** — 2.2 % more area and 6.4 % less clock. That is the entire cost of
using the ladder that actually wins at 5 bits.

The degree-4 cliff stands: 3 adders, 2.1× the area, Fmax down to 185 MHz. Nothing that survived
asks for it.

## B — fourth and fifth families

Downloads of GPT-2 and OPT-125m are in progress; a first attempt destroyed both weight files
through a `curl -f … || rm` guard followed by a resume against an already-complete file. Nothing
is measured yet, and the 3- and 5-bit claims still rest on three families.
