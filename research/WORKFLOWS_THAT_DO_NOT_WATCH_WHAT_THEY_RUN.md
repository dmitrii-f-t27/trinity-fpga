# Nine workflows run a script their `paths:` filters do not watch

Recommendation only. No workflow file is edited here — every one of the nine belongs to
a line that owns its own CI, and a silent change to someone else's trigger is worse than
the gap it closes. What follows is the exact one-line addition each needs.

## What the defect is

A workflow with `push: paths:` filters runs only when a changed file matches a pattern.
Nine workflows in this tree run a **tracked script** that no pattern matches. Edit the
script, and the job that executes it does not run. It keeps re-running whatever version
last happened to touch a watched file.

This is not hypothetical. It is how it was found:

> Pass 183 fixed `conformance/wrapper_fsm_audit.py` — the allow-list defect that made it
> flag 40 of 93 wrappers. The commit landed on `main`. `wrapper-fsm-sim.yml`, whose first
> step runs that script, **did not run**. Its filters watch the Verilog and the
> testbenches, not the audit. The fix had to be dispatched by hand to be seen at all.

A gate that cannot be triggered by fixing the check it runs is a gate whose result is
always from an older check than the one in the tree.

## Why the existing gate missed it

`research/audit_workflow_paths.py` has watched the Verilog side of this since it was
written: does a synthesis job watch the sources it reads? It did not check scripts. Worse,
it had already *noticed* the case and filed it as out of scope:

```python
# A job that hands synthesis to a script names nothing itself, so its
# watches cannot be matched here. ... Reported as a limitation rather
# than a finding, because it is one.
```

That comment is honest about the boundary and wrong about the boundary being necessary.
"Does it watch the script it runs?" needs no understanding of what the script does — only
whether its path appears among the patterns. The check now does both halves and has a
negative control for each.

Three of the nine are **the campaign's own gates** — `module-loader-gate`,
`reproducibility-gate`, `stale-citation-gate`. The tooling built to catch stale checks was
itself not re-run when its checks were fixed. That is the same shape as the defect, one
level up, and it is the reason this file leads with it rather than burying it.

## The nine, and the line each needs

Add the script to the workflow's `paths:` block. Additive only: widening a filter can make
a job run more often, never less, and cannot change what the job does when it runs.

| workflow | add to `paths:` |
|---|---|
| `ax7203-trinet-node-v2.yml` | `conformance/trinet_mac32_conformance_ax7203.py` |
| `conformance-frame-alignment.yml` | `conformance/frame_alignment_check.py`, `conformance/gfternary_compute_conformance_ax7203.py`, `conformance/trinet_mac32_conformance_ax7203.py` |
| `conformance-selftest.yml` | `conformance/compute_golden_consistency.py`, `conformance/corona_decode_host_ax7203.py`, `conformance/golden_consistency.py` |
| `lut-report.yml` | `fpga/openxc7-synth/run_synth.py` |
| `module-loader-gate.yml` | `research/audit_module_loaders.py` |
| `reproducibility-gate.yml` | `research/audit_reproducibility.py` |
| `stale-citation-gate.yml` | `research/audit_stale_citations.py` |
| `trinet-portability.yml` | `conformance/portability_check.py` |
| `wrapper-fsm-sim.yml` | `conformance/wrapper_fsm_audit.py` |

Shape of the edit, using `wrapper-fsm-sim.yml`:

```yaml
     paths:
       - 'fpga/openxc7-synth/corona_decode_*_ax7203.v'
       - 'formal/wrapper_uart_sim_tb.v'
+      # the script this job runs: fixing the check must re-run the check
+      - 'conformance/wrapper_fsm_audit.py'
```

A blanket `conformance/**` or `research/**` would also close it, and would trade a
precise trigger for a noisy one. Naming the script keeps the filter saying what the job
actually depends on.

## Verifying the count yourself

```
python3 research/audit_workflow_paths.py
python3 research/audit_workflow_paths.py --self-check
```

The self-check injects `run: python3 research/audit_workflow_paths.py` into a workflow
that currently passes, requires the audit to flag it, restores the file, and asserts the
restored bytes are identical. A clean sweep from a probe that cannot see anything is worth
less than no sweep.

## What this does not check

- **`workflow_dispatch`-only jobs.** No filters to be wrong about.
- **Scripts a script runs.** Only paths named in a `run:` line are read. A wrapper that
  shells out to a second script hides that second one from this check.
- **Untracked paths in `run:` lines.** Deliberately dropped — a generated or mistyped path
  is not something `paths:` could watch, and counting it would inflate the number with
  entries no edit could fix.
- **Whether running more often is wanted.** The check reports a trigger that cannot fire
  on its own input. Whether the owner wants it to fire is the owner's call.
