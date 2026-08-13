# Measurement records backing the TNF paper

Every file here is a machine-written record produced by a script in this
repository, copied verbatim. Nothing in this directory was edited by hand.

| file | what it records | status |
|---|---|---|
| `tnf_downstream_bayesian_si_2026-08-13.json` | outcome of one numerical task (MAP estimate of the solar gravitational parameter in raw SI) rather than a round-trip error; backs the downstream table | current |
| `gen_downstream_bayesian_si.py` | the generator for the above; deterministic under seed 20260813 | current |
| `strict_range_2026-08-13g.json` | per-workload comparison under strict representability against range bounds; backs the qualifying-pair count | current |
| `workloads_strict_2026-08-13g.json` | the workload/rung pairs and their ratios | current |
| `per_rung_2026-08-13g.json` | per-rung threshold sweep; backs the rung-threshold table | current |
| `centering_2026-08-13f.json` | rescaling invariance test that removed the absolute-magnitude window | current |
| `inside_window_2026-08-13f.json` | rows inside the window | current |
| `gpt2_window_2026-08-13e.json` | GPT-2 block-0 intermediates, the negative result inside neural inference | current |
| `crossover_2026-08-13e.json`, `crossover2_2026-08-13e.json` | crossover computation before and after the straight-line fit was withdrawn | second file current |

Two earlier records are deliberately **not** copied here: an invariance record
whose harness tested representability against zero rather than against the range
bounds, and the pre-fix workload sweep taken with the same harness. Both are
superseded by the files above; the defect and its consequences are stated in the
paper rather than hidden.
