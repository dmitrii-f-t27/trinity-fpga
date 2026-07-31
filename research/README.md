# Reproducing the numbers in this directory

Every claim recorded in `specs/numeric/*.t27` and cited in
`VERIFICATION_DOSSIER.md` comes from a script here. This file says how to re-run
each one and what it should print.

It exists because of a defect found in this campaign's own work: pass 51 tried to
re-run the ml_dtypes cross-validation on a clean machine and got an `ImportError`
instead of a number. The claim was true — it reproduced exactly once the dependency
was installed — but nothing said a dependency was needed. A result that holds only
in the environment that produced it is weaker than one that says what it requires.

## Dependencies

Measured by AST across all 15 scripts, so lazy imports inside functions are
included:

| script | needs |
|---|---|
| `crossval_ml_dtypes.py` | `ml_dtypes==0.5.4`, `numpy` |
| `format_benchmark.py`, `head_to_head.py` | `conformance/gf_ref.py`, `conformance/tekum_ref.py` (in-tree) |
| **the other 12** | **Python standard library only** |

So the third-party surface is one script. For that one:

```bash
python3 -m pip install 'ml_dtypes==0.5.4' numpy
```

Prefer an isolated environment — nothing here needs to be installed system-wide.

Two scripts additionally consume data produced by a C bridge (`libtakum_bridge.c`)
and take their input paths as arguments; see their docstrings for the exact `cc`
invocation. They are not runnable without a built libtakum, and say so on exit 2.

## What each script should print

Run from the repository root.

| script | expected result | exit |
|---|---|---|
| `verify_phi_rule.py` | `catalogued GF formats satisfying the rule: 17/17` | 0 |
| `verify_lucas_exact.py` | identity holds for every n in 1..256 at 500 digits; worst residue `4.000E-392` at n=256 | 0 |
| `crossval_ml_dtypes.py` | `total codes compared: 66224   divergences: 0` (14 zero-sign codes excluded) | 0 |
| `verify_oracle_exactness.py` | all 12 uncaveated oracles return exact carriers | 0 |
| `verify_extended_expansion.py` | `double_double` and `quad_double` hold non-overlap | 0 |
| `verify_quire_associativity.py` | locates the documented boundary; not a defect report | 0 |
| `gen_conformance_pack.py` | regenerates a pack | 0 |
| `verify_arithmetic_invariants.py` | commutativity etc. across families; **slow** — see below | 0 |

### Scripts that exit non-zero on purpose

A non-zero exit here means *the script found what it was built to find*, not that
it failed:

| script | exit | why |
|---|---|---|
| `verify_negation_invariant.py` | 1 | a family violates its own encoding's negation rule — the finding is the point |
| `audit_generated_packs.py` | 1 | reports the unresolved tekum oracle question |
| `crossval_libtakum.py` | 2 | missing input: needs the C bridge's TSV files as arguments |
| `proto_takum_decode_log.py` | 2 | same — takes a TSV path |

### The one genuine caveat

`verify_arithmetic_invariants.py` samples `K = 24` codes per format and tests all
`24 × 24 = 576` ordered pairs. Cost is `O(k²)` per format with exact rational
arithmetic, and on the wide GoldenFloat rungs a single multiply is enormous — it
did **not** complete within 600 s on an arm64 Mac. Budget accordingly, or expect
the same non-termination recorded in
`specs/numeric/arithmetic_invariant_sweep.t27` for gf64 and above.

## Reading the results

Each script prints its own scope limits, and several print the reason a result is
weaker than it looks (`sampled, not exhaustive`; `verifies the identity, not the
implementation`). Those lines are part of the result — the specs quote them rather
than the headline number alone, and anyone citing these figures should do the same.
