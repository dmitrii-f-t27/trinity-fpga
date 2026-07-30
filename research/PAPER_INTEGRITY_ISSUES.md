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

---

## G. Loop-3 findings (2026-07-30) — central "505 = 505" claim is mislabeled

### G1. GF16 MUL = 587, NOT 505 — the paper contradicts itself — HIGH
Reading `paper.tex` directly (no retelling):
- `paper.tex:863` — the LUT table: `16 & 6 & 9 & 485 & 587` → **plain GF16 MUL = 587 LUT**.
- `paper.tex:864` — `GF16+ (Quire) & 6 & 9 & 485+75 & 505+75` → **GF16+(Quire) MUL = 505 LUT**.
- `paper.tex:882-886` and `:890-894` — the prose: *"takum16 … 505 LUT — identical
  to **GF16 MUL (505 LUT in the zero-DSP regime)**"* and *"GF16 multiply … yield
  ≈505 LUT at W=16"*.

So the headline **"encoding equivalence 505 = 505"** is actually
**takum16 MUL (505) == GF16+(Quire) MUL (505)**, while **plain GF16 MUL = 587**.
The prose conflates "GF16" with "GF16+ (Quire)". A reviewer reading line 863
(GF16 MUL=587) and line 884 (GF16 MUL=505) sees a direct contradiction.
**Action:** in the prose (`:884`, `:893`, abstract `:56`, conclusion `:1297-1298`)
say "GF16+ (Quire) MUL = 505 LUT" wherever the equivalence is drawn, and keep
"plain GF16 MUL = 587" as the standalone datapoint. Same fix in
`research/COMPETITIVE_ANALYSIS_number_formats.md` §2/§5 (which I authored and
which propagated the "GF16 MUL 505" mislabel).

### G2. Vasilev-Floor coefficient 1.55 vs 1.63 — MEDIUM
- `research/COMPLETE_LUT_TABLE.md:34` — *"ADD: LUT = 1.55 × W² (R² = 0.876)"*.
- `paper.tex:877` — *"ADD = 1.63W² (R²=0.97)"*.
Two regressions of the same data give two coefficients and two R². (The earlier
audit in §A4 already flagged "two inconsistent regressions 1.55/2.06 vs
1.63/2.09"; here it is re-confirmed with exact line refs.) **Action:** pick ONE
regression (state the point set: W=4..24, N=11 for ADD) and use it in both the
paper and COMPLETE_LUT_TABLE; the other becomes a retracted draft.

### G3. MUL-LUT data EXISTS — my own §A4 was imprecise — correction
My §A4 said "MUL-LUT shows '---' (missing)". Verified now: MUL-LUT is present
for W≤32 in BOTH `paper.tex:859-867` (GF4..GF32 MUL: 7/174/365/454/587/851/1117/1860)
and `COMPLETE_LUT_TABLE.md`. The '---' only starts at W≥48 (GF48/64/96/128 have
ADD but no MUL). So the real gap is narrower than §A4 implied: **MUL-LUT is
measured only up to W=32; W=48..128 MUL is extrapolated from the scaling law.**
**Action:** either measure W=48/64/96/128 MUL (the mul cores exist) or label
those rows "est." in the table. (This loop's `scripts/lut_measure.sh` is built
to fill exactly this — see below.)

### H. Loop-3 measurement — paper LUT numbers are NOT reproducible (~3× low) — HIGH

`scripts/lut_measure.sh` (fixed: taps combinational `result_comb` via `-DFORMAL`,
pins explicit E/M per format) run for GF4..GF64 + direct as-top checks. Every
measurement of the SAME cores on the SAME flow (yosys 0.63, same git sha) gives
~3× the paper's headline numbers:

| core / method | measured (this loop) | paper / LUT_COMPARISON doc |
|---------------|----------------------|----------------------------|
| `gf_adder_param` GF14-default, as-top, no-flatten | **1338** | doc claims "GF16 = 486" |
| `gf_adder_param` GF16, registered-as-top wrapper | **1803** | paper GF16 ADD = 485 |
| `gf_adder_param` GF16, `result_comb` FORMAL-tap | **1689** | — |
| `gf_mul_param` GF16, registered-as-top wrapper | **1989** | paper GF16 MUL = 587 |
| `gf_mul_param` GF16-default, as-top | **692** | — |
| `gf_mul_param` GF16, `result_comb` FORMAL-tap | **1953** | — |

The cleanest reproduction attempt — `gf_adder_param` read as-top with default
params, `synth_xilinx -abc9 -nocarry -arch xc7` (no -flatten), yosys 0.63 — gives
**1338 LUT** (stable LUT2..6 distribution: 234/303/219/270/312), while
`LUT_COMPARISON_MEASURED.md` reports **486** for the same core/flow/version.
Same git sha of yosys. **2.75× discrepancy, reproducible on my side.**

Conclusions:
1. **`-flatten` is irrelevant** (flat == noflat for every format GF4..GF64;
   confirmed in `scripts/lut_measure.out`). Retract the §E2.2 flatten hypothesis.
2. **The param-default trap (§E2.1) is real**: `gf_adder_param` default = GF14.
3. **The paper's LUT table (`paper.tex:859-872`) and scaling law `1.63·W²` rest on
   numbers that are ~3× too low vs the current toolchain and are NOT reproducible**
   by any standard method (as-top, registered-wrapper, or FORMAL-tap). The most
   likely provenance: an older yosys build or a now-retracted smaller GF16 core.
   The "505 = 505" equivalence (takum16 vs GF16+) is therefore also unverified.

**Action (binding, escalated):** the arXiv LUT claims (table `paper.tex:859-872`,
the `2W²`/`1.63W²` law, the "505=505" encoding equivalence, and
`LUT_COMPARISON_MEASURED.md`) must be either (a) **fully re-measured** with the
pinned `scripts/lut_measure.sh` and the table rewritten with the real (~3× higher)
numbers, or (b) the provenance of 485/587/486 traced via git archaeology and the
exact historical core + yosys build reproduced. Until then the entire LUT-law
axis is `[measured, NON-reproducible]` — the most severe open integrity issue.

Pinned datapoints (this loop, `scripts/lut_measure.out`, FORMAL-tap wrapper,
LUT = sum LUT2..LUT6, yosys 0.63):
GF4 add45/mul8, GF6 384/453, GF8 627/612, GF10 735/918, GF12 1119/1203,
GF14 1254/1569, GF16 1689/1953, GF20 2175/2838, GF24 3003/3663, GF32 4302/5937,
GF48 8643/13038, GF64 add 13842.

### I. Provenance RESOLVED — paper numbers are the DEDICATED cores, not parametric

After measuring the dedicated (non-parametric) GF16 cores as-top, the paper's
numbers fall right into the dedicated-core family — the ~3× gap of §H was a
**core-mismatch**, not wrong numbers:

| dedicated core (as-top, yosys 0.63) | ADD-flow LUT | MUL-flow (-nodsp) LUT |
|-------------------------------------|-------------:|----------------------:|
| `gf16_adder.v`  | 786 | 753 |
| `gf16_add.v`    | 552 | 597 |
| `gf16_mul.v`    | 414 | 432 |
| `gf16_multiplier.v` | 81 | **483** |

vs the paper: GF16 ADD = **485**, GF16 MUL = **587**, "505" GF16+(Quire)≡takum16.
- `gf16_multiplier.v` MUL-flow = **483** ≈ the paper's central **"505"** encoding-
  equivalence claim (within yosys-version drift). **This is the provenance of 505.**
- The paper's GF16 ADD=485 / MUL=587 sit squarely in the dedicated-core range
  (432–786), NOT the parametric range (1689–1989).

**Refined conclusion (supersedes §H's "non-reproducible"):** the paper's LUT table
is consistent with the **dedicated** GF16 cores (`gf16_add`/`gf16_mul`/
`gf16_multiplier`), which are ~3× smaller than the **parametric**
`gf_adder_param`/`gf_mul_param` cores (the parametric ones carry GF4..GF64
generality + denormal/NaN/Inf overhead). The reproducibility gap was measuring the
wrong core.

**Action (binding, refined):**
1. The paper's LUT table must **name the exact core** per row (dedicated
   `gf16_add`/`gf16_mul` vs parametric `gf_*_param`) — right now `paper.tex:857`
   just says "ADD LUT / MUL LUT" with no core identifier, so a reader cannot
   reproduce.
2. The scaling law `1.63·W²` is the **dedicated-core** law; the parametric cores
   follow a steeper law (~3× higher, see `scripts/lut_measure.out`). State which.
3. `gf16_multiplier.v` (483 ≈ 505) is the source of the "505=505" equivalence —
   cite it explicitly instead of the ambiguous "GF16 MUL".
4. The parametric `gf_*_param` cores (the ones actually used in the corona_ HW
   cells and the Vasilev-Floor wide-format table) are ~3× bigger than the paper's
   dedicated-core numbers — so the wide-format rows (GF48/64/96/128 ADD 2791/4289/
   8642/14894 in `paper.tex:868-871`) need a core identifier too, or they may be
   parametric-core numbers mis-compared against the dedicated GF16 baseline.

### Note on gf512 / gf1024 (horizon-A remainder)
`COMPLETE_LUT_TABLE.md:27-28` shows GF512/GF1024 ADD ≈ 406k / 1.6M LUT (401% /
1605% of the FPGA) — **purely theoretical, exceed any current FPGA**. So their
SW-bitexact decode is provable (the mpmath/integer/RTL technique scales), but
they can never be Tier-E (silicon) — worth stating in the paper so the
"horizon-A" decode work is not read as a silicon claim.
