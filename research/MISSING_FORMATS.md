# Missing formats — oracle coverage of the 83-format catalog

**AGENT F (conformance) finding.** Verified 2026-07-15 against:
- SSOT catalog `specs/numeric/formats_catalog.t27` (repo `gHashTag/t27`, master — 83 `// CATALOG: id=` records, no dupes; family count 13).
- The 12 oracle modules in `conformance/`: `gf_ref`, `tekum_ref`, `posit_ref`, `bf16_ref`, `fp8_ref`, `mxfp_ref`, `takum_ref`, `decimal_ref`, `ieee_ref`, `legacy_ref`, `lns_ref`, `int_ref` (72 `FORMATS` entries total).

> Companion to `conformance/generate_vectors.py` (now emits both `{format}_add.json` and `{format}_mul.json`). The generator's per-format seeds are op-independent, so ADD and MUL vectors exercise the **same** `(a, b)` input pairs.

---

## 1. TL;DR — the honest numbers

| Quantity | Count | Notes |
|---|---|---|
| Catalog rows (SSOT) | **83** | `formats_catalog.t27`, 13 families |
| Oracle format-names (12 modules) | **72** | what `generate_vectors.py` iterates |
| Catalog rows **covered** by an oracle | **60 / 83** | strict, by id (incl. `mxfp8` ← `mxfp8_e4m3`) |
| Catalog rows **without** an oracle | **23** | itemised in §3 |
| …of which are **structural / parametric / container** (no single S:E:M decode law) | **11** | §3A — correctly excluded |
| …of which are **concrete, addable in principle** | **12** | §3B — real gaps |
| Oracle format-names that are **NOT** catalog rows | **12** | §4 (tekum, unsigned ints, wider bfloats, …) |

**The naive "72 of 83 covered, 11 missing" is an arithmetic artefact** (`83 − 72 = 11`). It conflates two disjoint sets: the 72 *oracle format-names* and the 83 *catalog rows*. They are not subsets of each other. The rigorous diff is **60/83 covered, 23 missing**, of which **11 are structural** (the likely origin of the "11") and **12 are concrete gaps**.

---

## 2. How the diff was computed

1. Pulled the 83 `// CATALOG: id=…` records from the SSOT `formats_catalog.t27` (the catalog matrix `fpga/CATALOG_MATRIX_83.md` and the catalog paper draft do **not** enumerate all 83 by name; only the `.t27` SSOT does).
2. Imported each of the 12 oracle modules and listed `FORMATS.keys()` → 72 names.
3. Set difference. One fuzzy merge applied: the catalog row `mxfp8` is covered by the oracle entry `mxfp8_e4m3` (same Microscaling family / same element encoding, OCP MX v1.0). Unsigned-int oracle entries (`uint4/8/16/32`) map to the catalog's combined `int4/8/16/32` rows (catalog uses one `INTn / UINTn` row per width), so they do **not** add catalog coverage — they are extra granularity.

Reproduce:
```python
# in conformance/
python3 -c "import ...diff..."   # see git log; the script is inline in the audit
```

---

## 3. The 23 catalog formats without a 12-module oracle

### 3A. Structural / parametric / container / technique — 11 (cannot have a single uniform oracle)

These are correctly absent: they have no standalone `S:E:M` decode law. They are *applied atop a base format* or are *parametric frameworks*, so a bit-exact oracle is either undefined or parameter-dependent.

| # | Format | Cluster | Catalog `bits` | Why no oracle | Addable? |
|---|---|---|---|---|---|
| 1 | `block_fp` | CompressionTrick | 0 | Per-tile **shared exponent** applied atop a base int/float (Wilkinson 1963 / Darvish-Rouhani 2020). The block, not the element, is the unit. | No — container, not a format |
| 2 | `shared_exp` | CompressionTrick | 0 | Generalised BFP; same reason as `block_fp`. | No — container |
| 3 | `per_channel_scale` | CompressionTrick | 8 | INT8 + an fp32 **per-tensor/per-channel scale** (Jacob 2018 / TFLite). Decode requires the external scale. | No — container |
| 4 | `stochastic_rounding` | CompressionTrick | 0 | A **rounding technique**, not a format (`s=0 e=0 m=0`). Applied atop a base. | No — not a format |
| 5 | `minifloat` | Theoretical | 0 | **Parametric framework** "arbitrary E:M, ≤16 bits" (Higham 1996). It is the *design space* containing gf4/8/12/16, fp4/6/8 — not one format. | No — parametric |
| 6 | `tapered_fp` | Theoretical | 0 | **Parametric** tapered framework (Morris 1971); posit ancestor. No fixed layout. | No — parametric |
| 7 | `unum_i` | Theoretical | 0 | Gustafson 2015 — **tapered + ubound**, variable-length, interval-valued. | No — variable-length/interval |
| 8 | `unum_ii` | Theoretical | 0 | Gustafson 2016 — **SORN projective** lookup-table arithmetic; catalog itself flags "not GF-comparable". | No — LUT/set arithmetic |
| 9 | `q_format` | IntegerFixed | 0 | **Qm.n fixed-point parametric** (`bits=0`, `varies`). Needs `(m,n)` to instantiate. | No — parametric (instantiable, e.g. Q1.15) |
| 10 | `gf8_bfp` | GoldenFloat | 8 | GF8 element + **per-tile shared exponent** (§12.5 hybrid). Container atop GF8. | No — container atop GF8 |
| 11 | `gf_lns_hybrid` | GoldenFloat | 16 | **Dual-space** GF+LNS (mul in log-space, accumulate in linear). Two decode laws in one storage. | No — dual-space, not single-law |

These 11 explain the recurring "11" in the codebase's shorthand. They are **gaps by design**, not bugs to close (echoes the catalog paper's "15 structural by design").

### 3B. Concrete formats — addable in principle — 12 (real gaps)

These have a concrete bit layout and a real decode law; they simply have no entry in the 12 `*_ref.py` modules yet. Several already ship a **standalone decode-conformance script** (so decode is proven; only the unified add/mul oracle is missing).

| # | Format | Cluster | `bits` | Status today | Addable? | Effort |
|---|---|---|---|---|---|---|
| 12 | `nf4` | QuantTuned | 4 | NormalFloat 4-bit, 16-value **quantile table** on N(0,1) (Dettmers/QLoRA). Decoded by `nf4_decode.v` (Corona). | **Yes** | Low — 16-entry table oracle |
| 13 | `bcd` | IntegerFixed | 0 | Binary-coded decimal (4 bits/digit). Standalone `bcd_decode_conformance_ax7203.py` exists. | **Yes** | Low — integer-in-decimal |
| 14 | `ms_mbf32` | HistoricalVendor | 32 | Microsoft Binary Format single (pre-IEEE, bias 129). Standalone decode script exists. | **Yes** | Low — S:E:M |
| 15 | `ms_mbf64` | HistoricalVendor | 64 | MS Binary double. Standalone decode script exists. | **Yes** | Low — S:E:M |
| 16 | `gfternary` | GoldenFloat | 2 | {-φ, 0, +φ} ternary. Separate `gfternary_compute_conformance_ax7203.py` exists. | **Yes** | Low — 3-value table |
| 17 | `afp` | QuantTuned | 16 | Adaptive FP (Tambe 2020): 1\|8\|7 + **tensor shift**. Per-element decode = bf16-like once shift fixed. | **Yes (shift=0 reduces to bf16)** | Low–Med |
| 18 | `gf48` | GoldenFloat | 48 | GF rung, rule-derived (`e=18`), spec-only. | **Yes** | Med — extend `gf_ref` |
| 19 | `gf96` | GoldenFloat | 96 | GF rung, rule-derived (`e=36`), spec-only. | **Yes** | Med — wide poly mul |
| 20 | `double_double` | ExtendedFloat | 128 | Two binary64 (Bailey/Hida). Standalone decode script exists. | **Yes** | Med — two-error-free add (Knuth) |
| 21 | `quad_double` | ExtendedFloat | 256 | Four binary64. Standalone decode script exists. | **Yes** | High — multi-word |
| 22 | `gf512` | GoldenFloat | 512 | GF rung, rule-derived (`e=195`), extrapolation/no RTL. | **Yes** | High — 512-bit poly mul |
| 23 | `gf1024` | GoldenFloat | 1024 | GF rung, rule-derived (`e=391`), extrapolation/no RTL. | **Yes** | High — 1024-bit poly mul |

> Quick wins if the 72-module set is to grow toward the 83 ceiling: **`nf4`, `bcd`, `ms_mbf32`, `ms_mbf64`, `gfternary`** (all ≤16-bit or table-based, several already decode-proven). That would move strict coverage from 60 → 65 with low effort, leaving the genuinely hard multi-component/ultra-wide ones and the 11 structural.

---

## 4. The 12 oracle format-names that are NOT catalog rows

The 72 oracle names are **not** a subset of the 83 catalog ids. These 12 exist as oracles but have no matching catalog row:

| Oracle entry | Module | What it is | Catalog relation |
|---|---|---|---|
| `tekum8/16/32` | `tekum_ref` | Balanced-ternary tapered (Hunhold, arXiv:2512.10964) | **Not in catalog at all** — Trinity-internal study format |
| `bfloat24`, `bfloat32` | `bf16_ref` | Wider Brain-Float variants | Catalog lists only `bfloat16` |
| `mxfp8_e4m3` | `mxfp_ref` | The E4M3 element of MXFP8 | Maps to catalog row `mxfp8` (counted as covered) |
| `mxint8` | `mxfp_ref` | Microscaling INT8 element | Not a standalone catalog row (OCP MX int element) |
| `pdp11_float` | `legacy_ref` | PDP-11 float | Not in catalog (catalog has VAX/IBM/Cray/x87) |
| `x87_48bit` | `legacy_ref` | 48-bit x87 | Not in catalog (catalog has `x87_fp80`) |
| `uint4/8/16/32` | `int_ref` | Unsigned two's-complement | Fold into catalog's combined `INTn / UINTn` rows |

These are legitimate extra granularity (especially the unsigned ints and `tekum`); they just shouldn't be counted as catalog coverage.

---

## 5. The honest coverage claim (recommended wording)

For papers / READMEs, replace "72/83" with one of these, depending on what is being claimed:

- **Oracle breadth (what `generate_vectors.py` actually produces):**
  > "Bit-exact ADD **and** MUL conformance vectors for **72** numeric format-instances across 12 oracle modules — covering **60 of the 83** catalog rows strictly, plus 12 non-catalog variants (unsigned ints, tekum, wider bfloats, OCP MX elements)."

- **Catalog coverage (strict):**
  > "**60/83** catalog formats have a unified decode+add+mul oracle; **23** do not — **11** are structural/parametric/container formats with no single S:E:M decode law (correctly excluded), and **12** are concrete formats addable in principle (nf4, bcd, ms_mbf32/64, gfternary, afp, gf48/96/512/1024, double/quad_double)."

- **One-line honesty:**
  > "60/83 strict; 11 structural-by-design; 12 concrete gaps (5 low-effort)."

Never write "72/83" without this footnote — it double-counts non-catalog oracle variants and under-counts the structural formats.

---

## 6. Cross-references

- SSOT: `specs/numeric/formats_catalog.t27` (gHashTag/t27 master).
- Count erratum: `research/ERRATUM_arXiv_2606.09686_catalog_count.md` (the 84→83 E8M0 correction; E8M0 is a Microscaling **component**, not a standalone row — so it is rightly absent from both the 83 and the oracle set).
- Generator: `conformance/generate_vectors.py` (emits `_add.json` + `_mul.json`).
- Oracle modules: `conformance/{gf,tekum,posit,bf16,fp8,mxfp,takum,decimal,ieee,legacy,lns,int}_ref.py`.
- HW matrix: `fpga/CATALOG_MATRIX_83.md` (decode-HW 41, compute-HW 30 = 71/83 Tier-E on AX7203 — a different, HW-oriented axis from this oracle-oriented audit).
