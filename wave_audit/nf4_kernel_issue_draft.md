# nf4-kernel issue draft (for `gh issue create` in gHashTag/trios-trainer-igla)

> **PROMOTED → https://github.com/gHashTag/trios-trainer-igla/issues/217** (2026-07-03)
> Created via gh CLI (no sandbox needed). Do NOT recreate. Sandbox-return batch
> reduced 4 → 3 actions (only schedule_cron + 2× save_custom_skill remain).
>
> **English-only** per PR #65. Original draft preserved below for reference.

---

## TITLE

nf4 kernel does not train — delta_bpb=0.0 on all seeds/algos (matrix_samples.jsonl, run 28643449889)

---

## BODY

Summary: in PR #216 (run 28643449889, commit fab7d81, 2026-07-03) format `nf4` yields `bpb=7.0` exactly, `delta_bpb=0.0` across all seeds and both adamw+muon. Other formats move: fp8_e4m3/int4 delta 0.19-0.33, floats ~0.05 under muon.

Evidence table (hidden=96, step=3000):
- nf4 adamw/muon: 7.000000, delta 0.0
- fp8_e4m3 adamw: 6.668, delta 0.333
- int4 muon: 6.695, delta 0.304
- int8 muon: 6.903, delta 0.096
- gf16 muon: 6.975, delta 0.026

bpb=7.0 = untrained ceiling (log2 alphabet). Likely root cause: nf4 = hardcoded 16-value LUT (#97); if fake_quant nf4 snaps without scale/STE, gradients zero out (compare int4/int8 STE in #94/#96).

Note: all 88 rows have falsifier_2_hit=true → smoke-scale, not champion.

Acceptance:
- nf4 fake_quant gets scale + STE; nf4 delta_bpb > 0 under muon; OR
- mark nf4 inference-only and exclude from train-matrix.

Refs: PR #216, #94, #96, #97.
