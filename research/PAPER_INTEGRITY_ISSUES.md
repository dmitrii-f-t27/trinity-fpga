# Paper Integrity — verified issues & non-issues (audit 2026-07-24)

**Goal:** a list of items to strengthen the article
`research/arxiv_submission/paper.tex` (v4). **Every item is verified against the
primary source** (not against a retelling). Honesty requires separating real
problems from false alarms — see §B.

> Method: repo audit + independent grep-verification against `paper.tex` /
> `README.md` / `CATALOG_MATRIX_83.md`. Artifacts verified via `ls fpga/openxc7-synth/`.

---

## A. Real problems (must fix before arXiv-v5)

### A1. Internal contradiction in the GF14 verdict — HIGH
- `paper.tex:492` (robustness table): `GF14 … 0/4` (× × × ×).
- `paper.tex:971`: *"GF14 and above pass all four tests"*.
- `paper.tex:560` (hold-out table): `GF14 … 7/7`.
A reader cannot tell whether GF14 passes or fails. **Action:** reconcile — these
are different test-suites (robustness-4 vs hold-out-7); state explicitly in the
table captions which suite is which, and remove the categorical "pass all four"
in :971 or qualify it as "pass all four hold-out tests".

### A2. Decode Tier-E count mismatch (47 vs 41) — LOW
- `README.md:12`: `decode-HW Tier-E ~47/83`.
- `paper.tex:103-104`: `~41 of 83 … 41 decode ports`.
- `fpga/CATALOG_MATRIX_83.md:31`: `decode 41`.
Three sources, two numbers. **Action:** converge on one number (likely 41 — it is
in the paper and the catalog; update the README or clarify that 47 includes
compute cells, not only decode).

### A3. LUT numbers = yosys pre-P&R, no committed nextpnr `.rpt` — MEDIUM
- Already disclosed in `paper.tex:1236-1239` (Threats to Validity, *"15–30%
  post-PnR inflation"*). Honest, but no artifact.
- There is no nextpnr `.rpt` utilization file in `fpga/openxc7-synth/` (only
  `test_r23_nextpnr.xdc`).
**Action (article-strengthening option B):** one end-to-end nextpnr run for
GF16/posit16 ADD/MUL + commit `.rpt` → turns "disclosed limitation" into
"measured post-PnR".

### A4. "Vasilev Floor" 1.63/2.09 W² — yosys-stat only — MEDIUM
- `SESSION_REPORT_2026_07_17.md:32` honestly tags it `[yosys-stat, NOT post-P&R]`.
- In the paper (`paper.tex:856-874`) the ADD-LUT table for W=48/64/96/128 is given,
  MUL-LUT shows "---" (missing), no P&R report.
**Action:** either add the MUL-LUT to the table (mul cells exist), or explicitly
state "the floor is formulated for ADD; MUL will follow in v5".

### A5. Small silicon samples (64–512) — LOW (already partly disclosed)
- `README.md:83`: *"Vector counts vary by run (64–512 sampled; GF4 exhaustive at
  256)"*. This is not visible in the abstract.
**Action:** one sentence in §Methodology: "bit-exact proven on representative
sweeps of 64–512 vectors per format (GF4 exhaustive)", so a reviewer does not read
"0 failures" as exhaustive.

---

## B. False alarms (verified — the paper is honest here, do NOT "fix")

It is important to record these so that nothing correct gets "corrected".

### B1. takum16 MUL = 505 LUT — the artifact EXISTS ✓
A sub-agent audit claimed "no committed takum16_mul.v". **Wrong:** `fpga/openxc7-synth/`
contains `takum16_native_mul.v`, `takum16_mul_top.v`, `takum16_native_mul_tb.v`,
`takum16_mul_vectors.txt`. The central claim "encoding equivalence 505 = 505"
(`paper.tex:363,882`) rests on a real RTL. **Remaining (soft):** commit the yosys
report from which exactly 505 is derived, so the number is reproducible — but this
is not an integrity gap.

### B2. GF64 — the paper is honest ✓
`paper.tex:106,378,943,953`: GF64 is explicitly "70.1% (359/512), NOT bit-exact,
reported honestly", the cause (barrel-shifter clamp / timing) explained. The
abstract correctly says "GF4–GF32 … bit-exact" — GF64 is NOT in that list. No
overstatement.

### B3. "72 formats" — substantiated ✓
`MISSING_FORMATS.md:17` and 287 JSONs in `conformance/vectors/` confirm ~72 unique
formats. The caveat (12 oracle names that are not catalog rows, `MISSING_FORMATS:90`)
is soft; for the paper a disclaimer "72 oracle formats, 83 catalog rows (11
structural-by-design without a decode law)" is enough.

---

## C. Self-corrections already made by the project (context for a reviewer)

These retractions show the project can roll back honestly — worth stating
explicitly in §Threats to Validity as "reproducibility discipline":
GF+ v1 retracted (`c86097181`), 84→83 erratum (E8M0), φ-rule downgraded to a
heuristic (`af65d907c`), DIV/SQRT=binary32-proxy (`DIV_SQRT_HONESTY.md`), 6
subnormal suspects retracted, fake CI workflow deleted, GF4/GF8 "exhaustive on HW"
downgraded to [needs confirmation].

## D. Priority for the next pass
1. **A1 (GF14)** — text edit, 10 minutes, removes a direct self-contradiction.
2. **A2 (count)** — text edit, 5 minutes.
3. **A3/A4 (P&R + MUL-LUT)** — experiment (see article-strengthening options in
   the loop report), gives the paper a qualitatively new evidence tier.

---

## E. Loop-2 findings (2026-07-24) — after attempting Option A (GF-vs-posit LUT)

### E1. "posit16 mul" cell = binary32 proxy — HIGH for any format comparison
`fpga/openxc7-synth/corona_compute_posit16_mul_ax7203.v:132` instantiates
```
gf_mul_param #(.EXP_BITS(8), .MANT_BITS(23), .HAS_INF(1)) u_comp ( ...)
```
i.e. **binary32 (E8M23), not a native posit multiplier**. The same pattern as
DIV/SQRT (`DIV_SQRT_HONESTY.md`). The standalone posit RTL in the repo is only
`posit{8,16,32,64,128}_decode.v` (decode); **there is no native posit add/mul
core**. **Consequence:** a fair GF-vs-posit LUT head-to-head for ADD/MUL is
**impossible from the existing cores** — a real posit multiplier must be ported
first (a separate task). For the paper: state explicitly that posit is decode-only
on HW; any "format-cost" citation for posit must take LUT from the literature
(PACGen: posit32 mul ≈1.1–2.7k LUT), not from a repo core. The measured table
(`LUT_COMPARISON_MEASURED.md`) correctly does NOT include posit — this is already
honest.

### E2. LUT numbers are fragile w.r.t. flow/params — MEDIUM (reproducibility)
A fresh measurement on yosys 0.63 (the same version as in the doc):
- `gf_adder_param` with **default params** (E6M**8** = GF14!) + `-flatten` →
  **1338 LUT**, vs the documented **486 LUT** (GF16, no `-flatten`).
The discrepancy is explainable, but it exposes 3 reproducibility risks:
1. **Inconsistent defaults of the parametric cores:** `gf_adder_param` default
   `MANT_BITS=8` (→GF14), `gf_mul_param` default `MANT_BITS=9` (→GF16). Anyone who
   synthesizes `gf_adder_param` with defaults gets GF14, not GF16. **Action:** align
   the defaults (both = GF16) OR commit a param-pinning wrapper/script.
2. **`-flatten` gives a 2–3× different LUT** than no-flatten (in my run, larger;
   the abc9 global optimizer is sensitive to flatten). The paper methodology fixes
   `-flatten` for ADD — so all headline numbers MUST be measured with `-flatten`
   uniformly; `LUT_COMPARISON_MEASURED.md` measured WITHOUT `-flatten` → a mismatch
   between the paper methodology and the measurement doc.
3. **abc9 nondeterminism** — the LUT2..LUT6 distribution "floats" between runs (the
   sum is more stable than the distribution).
**Action (article-strengthening option A):** commit one `scripts/lut_measure.sh`
that, for each format, explicitly instantiates a wrapper with the correct E/M and
pins ONE flow (matching the paper methodology `-flatten -abc9 -nocarry [-nodsp]
-arch xc7`), and commit its output table next to it. Then "505 LUT" / "486 LUT"
become reproducible via `bash scripts/lut_measure.sh`, not just "trust the doc".

### F. Closed by this loop (not paper-integrity, but horizon-A)
gf256 → strict SW-bitexact (3 witnesses, 50230/50230). Horizon-A: SW-bitexact
72→73, remaining selfconsistent 3→2 (`gf512/1024`). See
`conformance/README_gf256_bitexact.md`.
