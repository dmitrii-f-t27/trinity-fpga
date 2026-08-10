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
