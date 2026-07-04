# Erratum — arXiv:2606.09686 (numeric format catalog): format count 84 → 83

**Status:** correction notice, ready for arXiv v2 / citation.
**Applies to:** arXiv:2606.09686, original draft.
**Date:** 2026-07-04.

## Correction

The original draft of arXiv:2606.09686 states the numeric format catalog comprises
**84** formats. The canonical count is **83**.

**Authoritative source of truth:** `INDEX_all_formats.json` in repository `gHashTag/t27`
(master HEAD `92f3506`, verified 2026-06-28), field `total_formats = 83`. This is the
single source of truth referenced by `fpga/CATALOG_MATRIX_83.md` and by the hardware
conformance evidence chain on `gHashTag/trinity-fpga#199`.

## What to change for arXiv v2

- Replace every occurrence of "84 formats" / "84-format catalog" / "eighty-four" → **83**.
- Add the SSOT citation: *catalog defined by `INDEX_all_formats.json` (gHashTag/t27),
  83 formats*.
- In any table that enumerates formats, the row count must total 83, not 84.

## Why the earlier count was off (honest note)

The earlier "84" was a pre-finalization draft count. We do **not** claim a specific
off-by-one mechanism (doing so without evidence would compound the error). What is
verifiable: the SSOT `INDEX_all_formats.json` enumerates exactly 83 unique format IDs,
and that file is the canonical reference against which all downstream artifacts
(`CATALOG_MATRIX_83.md`, the FPGA Tier-E evidence on #199, the leaderboard) are
reconciled.

## Related discrepancy (NOT this erratum, but flagged for reviewers)

A *separate* count discrepancy exists between (a) unique catalog IDs and (b) RTL cells
in `gHashTag/trinity-fpga`: the FPGA repo carries decode cells `bitnet`, `e8m0`, `mxint8`
that are **not** separate catalog IDs (their decode role is covered by adjacent catalog
entries). This inflates a naive RTL-cell count relative to the 83 unique catalog IDs.
This is a cell-vs-ID accounting difference, **not** a catalog-size error — the catalog
size is 83 regardless. Documented here so reviewers do not conflate the two.

## Downstream artifacts already consistent with 83

- `fpga/CATALOG_MATRIX_83.md` — 83 (filename + body).
- `gHashTag/trinity-fpga#199` EPIC — Tier-E ceiling framed as 71/83 (terminal on AX7203).
- FPGA format leaderboard (2026-07-04) — 83 total, 47 Tier-E unique-ID, 71 Tier-E repo-methodology.
- `research/goldenfloat-hw-conformance/GOLDENFLOAT_HW_CONFORMANCE_v0.2.md` §1 — already
  cites "83 formats [arXiv:2606.09686; erratum correcting an earlier count of 84]".
