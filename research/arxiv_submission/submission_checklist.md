# arXiv Submission Checklist — "83 Number Formats on Open-Source Silicon"

**Paper:** `research/CATALOG_PAPER_DRAFT.md`
**Target category:** `cs.AR` (Hardware Architecture); secondary `cs.ET`
**Author:** Dmitrii Vasilev — ORCID 0009-0008-4294-6159
**Comments field for arXiv:** `83 formats, openXC7, Artix-7`

---

## Pre-submission honesty audit

- [x] Abstract ≤ 200 words (verified: `wc -w abstract.txt` — see below)
- [x] No "first / best / only / novel format" claims anywhere in draft or abstract
- [x] GF64 reported as **"70.1% silicon (359/512), timing-closure issue in the 43-bit barrel shifter"** — NOT bit-exact
- [x] GF compute claim is **"10 GF formats (GF4–GF32) × {ADD,MUL} bit-exact"** — 20 cells total
- [x] φ-ratio described as **"design heuristic"** — not a theorem (Introduction §1, §2.4, §7)
- [x] LUT-only reported as a **toolchain constraint** (partial DSP48E1 docs), not a design preference
- [x] MXFP8 standalone weakness attributed to its block-scaled design context
- [x] No competitive ML-throughput claim (scaling to full attention blocks stated as unproven)

## arXiv metadata

- [x] Category: `cs.AR`
- [x] Cross-list: `cs.ET` (optional secondary)
- [x] Comments: `83 formats, openXC7, Artix-7`
- [x] Author ORCID: 0009-0008-4294-6159 (Vasilev)
- [x] License: arXiv default (CC-BY 4.0 or arXiv non-exclusive) — pick at submit
- [x] Abstract text = `abstract.txt` (paste into submission form; no markdown, no LaTeX)

## Bibliography

- [x] All 15 cited works in `paper.bib` with arXiv eprint fields
- [ ] **Verify every arXiv ID resolves on arxiv.org/abs/<ID>** before submit.
      Known real / verifiable IDs: 2404.18603 (takum), 2408.10594 (takum codec),
      2310.10537 (MX), 2209.05433 (FP8), 2208.09225 (FP8 quant), 2311.12359
      (Aggarwal FPL), 1908.01466 (PERI), 2402.17764 (BitNet b1.58).
      **Placeholder / author-self-assigned IDs requiring verification:**
      2512.10964 (tekum), 2603.08741 (AetherFloat), 2605.06875 (EULER-ADAS),
      2606.05017 (GoldenFloat), 2606.09686 (Catalog), 2607.03652 (ELiTeFormer),
      2607.01607 (MxGLUT). If any does not resolve, replace with a permanent
      URL (e.g. GitHub release, Zenodo DOI) or drop the citation.
- [x] No broken `\cite{}` keys — every `\cite{X}` in the paper resolves to a
      `@misc{X, ...}` / `@inproceedings{X, ...}` entry in `paper.bib`

## Source files to upload

- [x] GF16 param_top wrapper committed at fpga/openxc7-synth/gf16_param_top.v
- [ ] Main TeX source (convert `CATALOG_PAPER_DRAFT.md` → `.tex`, or upload as
      a single `main.tex` with the markdown rendered to LaTeX sections)
- [ ] Convert CATALOG_PAPER_DRAFT.md to LaTeX (.tex) — arXiv requires PDF/LaTeX, not markdown
- [ ] `paper.bib`
- [ ] Figures (none in current draft; LUT/accuracy tables stay as tables)
- [ ] Reproducibility appendix pointers (`research/format_benchmark.py`,
      `research/format_accuracy_results.csv`, `research/lut_comparison.md`)

## Specific numeric claims to re-verify against the repo before submit

- [ ] `71 / 83` formats carry ≥1 bit-exact silicon cell — cross-check
      `fpga/CATALOG_MATRIX_83.md` and EPIC #199
- [ ] `41 decode ports` count
- [ ] `10 GF formats` = GF4, GF6, GF8, GF10, GF12, GF14, GF16, GF20, GF24, GF32 × {ADD, MUL} = 20 cells
      (verify each is 16 cells, 0 failures (vector counts vary by run) or bit-exact on silicon logs)
- [ ] `359 / 512 (70.1%)` for GF64 ADD — cross-check
      `.trinity/experience/wave_2026_07_14_wave3.md` and the GF64 conformance
      UART log
- [ ] GF16 adder = 486 LUT (with -flatten: 491), mul = 94 LUT + 1 DSP (`BENCH-005_FINAL.md`)
- [ ] GF16 MAC-16 = 71 LUT + 16 DSP; ternary MAC-16 = 52 LUT, 0 DSP
      (`BENCH-006_RESULTS.md`)
- [ ] Takum16 decode = 0 LUT + 57 BRAM36 (measured)
- [ ] Decimal128 routes at 336-bit; takum64 119/140-bit multiply fails 32/32
      seeds, truncated 94/72-bit routes with 2 fails vs 5

## Self-check commands

```sh
wc -w research/arxiv_submission/abstract.txt            # must be <= 200
grep -niE '\b(first|best|only|novel|state[ -]of[ -]the[ -]art)\b' \
    research/CATALOG_PAPER_DRAFT.md                     # must return nothing relevant
grep -ni 'bit-exact' research/CATALOG_PAPER_DRAFT.md | grep -i '30 compute'   # must be empty
```

## Post-submit

- [ ] Stamp the arXiv ID into `research/CATALOG_PAPER_DRAFT.md` header
- [ ] Add arXiv ID to `docs/migration-map.md` / bibliography README
- [ ] Open issue to back-link from `formats_catalog.t27` repo
