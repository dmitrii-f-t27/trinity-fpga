# Ready-to-paste related-work subsection — measured, not asserted

> Produced 2026-07-31, pass 50. Fourth in the ready-to-paste series, after
> `ARXIV_ABSTRACTS_READY_TO_PASTE.md`, `ARXIV_BODY_FIXES_READY_TO_PASTE.md` and
> `README_SECTION_READY_TO_PASTE.md`.
>
> **Why this exists.** Pass 46 found Paper B's related-work treatment thin — it
> cites IEEE 754 [15] and Wintersteiger [11], but never positions the corpus
> against an existing published vector set. This gives it one, with every number
> measured from an artefact on disk.
>
> **Target:** Paper B, the related-work section, as a short subsection. Paper A can
> cite it rather than repeat it.
>
> **Honest limitation, stated up front:** web access was unavailable when this was
> written, so Berkeley TestFloat, the Posit Standard suites, libtakum's own tests
> and the OCP MX reference vectors were **not** surveyed. They are the obvious
> further comparables. What follows rests on one comparable, measured directly.

---

## Positioning against existing published vector sets

Published conformance vectors are not new; what varies is their shape. The most
widely deployed example is numpy, which ships 20 validation files of the form

```
dtype,input,output,ulperrortol
np.float32,0x80000000,0xff800000,3
```

Measured over numpy 2.4.4: **26,615 vectors**, covering **20 transcendental
operations** across **2 formats** (binary32 and binary64). Every row carries a
stated tolerance of 1–4 ULP. **None claims exactness.**

This corpus is the complement rather than the successor:

| | numpy validation sets | this corpus |
|---|---|---|
| vectors | 26,615 | 5,075 |
| formats | 2 | **83** |
| operations | 20 (transcendental) | 1 (decode/encode) |
| error claim | 1–4 ULP tolerance | **4,949 at abs_error = 0** |
| non-zero errors | every row | 112, disclosed via allowlist |

The corpus is broader by formats and exact where numpy states a tolerance; numpy is
deeper by vectors and covers an operation class the corpus does not touch at all.

**The reason for the difference is worth stating plainly, because it is not
rigour.** numpy's sets cover transcendental functions, where correctly-rounded
evaluation is not guaranteed by any common libm, so a tolerance is the only
defensible claim. This corpus covers decode and encode, which is decidable: an
exact rational either is or is not the value of a bit pattern. Exactness was
available here because of the operation class, not because of superior method.

That boundary shows up inside the corpus too. Its own `takum32` pack, checked
against libtakum (the format author's C99 reference), agrees on 3 of 15 vectors
bit-identically and differs by **exactly one ULP** on the other 12, never by more —
because a logarithmic decode requires `exp()`. Two unrelated artefacts, at very
different scales, mark the same frontier: bit-exactness is attainable over the
decidable class and stops at the transcendental one.

---

### Notes for whoever applies this

- The table is the part worth keeping if space is tight. It concedes the axis on
  which the corpus is smaller, which is what makes the rest credible.
- The last paragraph is the actual intellectual contribution — the corpus is
  bit-exact precisely where bit-exactness is decidable, and its own takum result
  locates the frontier from the inside. That is more useful to a reader than any
  novelty claim.
- Do **not** extend this into "the first exhaustive catalogue" or similar. Only one
  comparable was measured; TestFloat and the posit suites remain unexamined, and a
  survey claim would outrun the evidence.
- Every number above is reproducible: the numpy figures from
  `numpy/_core/tests/data/umath-validation-set-*.csv`, the corpus figures from
  `conformance/vectors/INDEX_all_formats.json` and the packs it lists.
  (`specs/numeric/related_work_measured.t27`)
