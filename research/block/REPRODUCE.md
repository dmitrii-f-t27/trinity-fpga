# Reproducing the LLM measurements in `research/block`

**This file is generated.** `python3 reproduce_index.py` rewrites it and
`MANIFEST.json` from the sources beside it; `--check` fails if either has drifted.
Every number below is computed at generation time. Nothing here is a
hand-maintained list, because a hand-maintained list is how an index and a tree
stop agreeing without either of them looking wrong.

## The three questions, and where each one stands

| | |
|---|---|
| *Which script produced this number?* | answered for **177 of 187** records |
| *Against which harness?* | **82 of 82** records naming one hash-match the file in this tree |
| *Against which checkpoint?* | **63** records pin a Hub revision; **63** agree with `main` today, **0** disagree |

Check the first two yourself, with no third-party package installed at all:

```
python3 verify_manifest.py
```

## What the harness check is worth, and what it is not

82 of the 187 records carry a `provenance` block. It was **retro-fitted on
2026-08-12** and says so in its own `RETROFITTED` field; the block is not
contemporaneous with the measurement. What it does give is a filename *and a
sha256* for the harness, and that pair is testable against this tree today:
**82 of 82 match, 0 differ.** They name one corpus across the whole set.

The corpus is pinned the same way and **its bytes are not in this repository**.
`block_tnf.py` reads `wikitext2-test.parquet` from a scratchpad directory that no
longer exists. What the records keep is the identity of what it read, and the
harness's own loader says exactly how to rebuild it -- read the parquet, take the
`text` column as a list, join with `\n\n`. So the claim is testable against the
public dataset in three lines:

```python
import hashlib
from datasets import load_dataset
rows = load_dataset("wikitext", "wikitext-2-raw-v1", split="test")["text"]
s = "\n\n".join(rows)
print(len(rows), len(s), hashlib.sha256(s.encode()).hexdigest())
```

Every provenance-bearing record in this directory claims that prints

```
4358 1294336 696cca6b65a171b0a358a4be6732cdfdf2dd6164a32e20fd70e3c13fc4dfae83
```

This package does not run that check: `datasets` is not a standard-library
module and nothing here installs one. The recipe is written down so that
testing the claim is three lines of somebody's afternoon rather than an
archaeology problem.

## Three gaps, stated before anyone has to find them

**1. The revision is where the weights were downloaded from, not proof of what
they contained.** The records say this themselves. `main` is a moving branch, so a
revision agreeing with it today is evidence and not proof. What makes the evidence
worth something here is that the newest of the 8 repositories was last modified on
**2025-02-06** -- before the provenance pass of 2026-08-12 -- so `main` has not
moved under any of them since. Probably, not certainly: the local copies were
deleted on 2026-08-12 and cannot be re-hashed.

**2. 57 of 162 sources contain a path that exists only on the machine that ran
them.** `campaignE_models.json` is the plainest case: every model it names lives
under a session scratchpad on a host that is gone. Those scripts cannot run from a
clone without editing the path first.

**3. 100 of 162 sources import torch or transformers**, so re-running them needs the
weights on disk. **53 import neither and read no foreign path** -- those run here,
immediately, and the next section is what happened when they did.

## What happened when the dependency-free scripts were re-run

`python3 rerun_dependency_free.py` copies this directory to a temporary
sandbox -- it never writes here -- runs each qualifying script, and compares
what it produces against the committed record leaf by leaf.

On Python 3.14.6: **53 scripts ran, 45 exited 0.**

**Only 13 of them write a record at all.** The rest print a verdict and exit,
so an exit code is all they leave behind. Read what follows as a statement about
**13 records**, not about 53 scripts -- the difference matters, and quoting the
larger number would be the more flattering of the two mistakes.

Of those 13 records: **9 byte-identical**, **4 differed**, and of those **3
differed in their `provenance` block and nowhere else** -- every computed value
reproduced.

That last figure is a finding, not a footnote. The provenance blocks were
added by a one-off pass; **the scripts that generate these records do not
write them.** So re-running a stats script silently strips the harness hash,
the corpus hash and the checkpoint revision from its own output -- the repair
undoes itself the first time anyone re-runs the thing it repaired. The
substantive differences, if any, are listed per record in `RERUN.json`.

Records whose *content* moved:

- `campaignE_frozen.json` (from `campaignE_predict.py`): 10 of 51 leaves differ, e.g. `/amended_utc`, `/amendment_P4/claim`, `/amendment_P4/information_state`

### The 8 that did not exit 0

A failure means different things depending on why, and the report separates
them rather than printing one number: **missing input 7**, **script error 1**.

- `campaignE_transfer.py` -- missing input: FileNotFoundError: [Errno 2] No such file or directory: './campaignE_score.json'
- `importance_theory.py` -- missing input: no checkpoints present yet
- `lineC_stats.py` -- missing input: missing ./lineC_gptneo.json -- a pre-registered checkpoint may not be dropped after the fact
- `loguniform_rotation.py` -- missing input: FileNotFoundError: [Errno 2] No such file or directory: './loguniform_x_smollm2.npy'
- `loguniform_theory.py` -- missing input: FileNotFoundError: [Errno 2] No such file or directory: './loguniform_x_smollm2.npy'
- `loguniform_verdict.py` -- missing input: FileNotFoundError: [Errno 2] No such file or directory: './loguniform_x_smollm2.npy'
- `real_weights_escape.py` -- missing input: no checkpoints present yet
- `u_verdict.py` -- script error: TypeError: list indices must be integers or slices, not str

`missing_input` is a gap in this repository: the named file is genuinely not
here, and the harness checks that before saying so -- if the source tree held
the file, the failure would be reported as `sandbox_gap` and would be about
the harness instead. `script_error` is a defect in the script. There is one,
and it is worth stating plainly rather than leaving in a JSON field:
`u_verdict.py` collects its input with the glob `u_surface_*.json`, and one
file matching that glob -- `u_surface_verdict.json`, written by
`u_surface_verdict.py` -- is a JSON list where the other fifteen are objects
with a `rows` key. It raises `TypeError` on the tree exactly as committed.
Left unfixed here on purpose: this package measures the directory, and a
package that repairs its subject before measuring it reports a tree that
does not exist.

## Records with more than one candidate producer

A general template and a specific script both write a name of this shape, and
the resolver will not guess between them.

- `align_u_tiefloor_gpt2.json` <- `align_u.py`, `align_u_tiefloor.py`
- `align_u_tiefloor_opt.json` <- `align_u.py`, `align_u_tiefloor.py`
- `align_u_tiefloor_pythia.json` <- `align_u.py`, `align_u_tiefloor.py`

## Records with no producer in this directory

Each is one of: an *input* rather than an output, a path built through a
construct the resolver does not evaluate, or a write to an absolute path on
another machine.

- `campaignD_kl15_smollm2_16win.json`
- `campaignD_kl15_smollm2_8win.json`
- `campaignE_models.json`
- `kurtosis_all.json`
- `u_theory_weights_qwen_pythia_partial.json`
- `u_theory_weights_smollm2.json`
- `zphi_acc_width.json`

## Models named in the sources and in the records

Resolved against the Hugging Face API, cached in `models_resolved.json`, refreshed
with `reproduce_index.py --models`. `lastModified` is the repository's own.

| id | `main` today | repo last modified | named by |
|---|---|---|---|
| `EleutherAI/gpt-neo-125m` | `21def0189f5705e2521767faed922f1f15e7d7db` | 2024-01-31 | 7 file(s) |
| `EleutherAI/pythia-160m` | `50f5173d932e8e61f858120bcb800b97af589f46` | 2023-07-09 | 15 file(s) |
| `HuggingFaceTB/SmolLM2-135M` | `93efa2f097d58c2a74874c7e644dbc9b0cee75a2` | 2025-02-06 | 15 file(s) |
| `Qwen/Qwen2.5-0.5B` | `060db6499f32faf8b98477b0a26969ef7d8b9987` | 2024-09-25 | 13 file(s) |
| `bigscience/bloom-560m` | `ac2ae5fab2ce3f9f40dc79b5ca9f637430d24971` | 2023-09-26 | 5 file(s) |
| `facebook/opt-125m` | `27dcfa74d334bc871f3234de431e71c6eeba5dd6` | 2023-09-15 | 18 file(s) |
| `gpt2` | `607a30d783dfa663caf39e06633721c8d4cfcd7e` | 2024-02-19 | 2 file(s) |
| `state-spaces/mamba-130m-hf` | `1e76775f628fbf1350fbe4dbb3d971ba64af25a1` | 2024-03-06 | 5 file(s) |

## How the producer of a record is decided

By walking the Python sources for *write sites* -- `open(p, "w")`,
`Path(p).write_text(...)`, `OUT`-ish assignments -- reducing each path
expression to a static shape, and matching that shape against the filenames
actually present. Local names are followed, because the ordinary write site here
is `open(dst, "w")` after `dst = os.environ.get("OUT") or os.path.join(...)`.

Read sites are excluded deliberately. Three scripts mention
`align_u_{tag}.json` and exactly one writes it; an index built from mentions
would name all three and be wrong about two.
