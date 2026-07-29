# Competitive Analysis — Trinity GoldenFloat (GF) vs alternative number formats

**Date:** 2026-07-24. **Context:** positioning the Trinity-GF family
(`gf8..gf1024`, parametric E/M/BIAS, φ-biased taper, bit-exact decode via 3-witness
mpmath/integer/RTL, claimed "Vasilev Floor" `LUT_ADD ≈ 1.63·W²`) for the arXiv
paper. The axis of competition is **FPGA LUT at fixed bit-exactness**.

Source data: web research (arXiv, OCP, vendor blogs) + a repo audit
(see `research/PAPER_INTEGRITY_ISSUES.md`).

---

## 1. Competitor map

| Format | Year | Idea | FPGA LUT evidence | Main weakness |
|--------|------|------|-------------------|---------------|
| **Posit** | 2017 / std 2022 | variable regime bits, taper near ±1 | **2–4× FP32 LUT** (add ≈0.9–2.5k, mul ≈1.1–2.7k LUT on Xilinx 7, PACGen/Chaurasiya) | regime decode (LZD+barrel-shift) dominates; coding-efficiency loss away from ±1; variable latency |
| **Takum** | 2024 (CoNGA) | logarithmic tapered, fixes posit's dynamic-range collapse | **NO published FPGA LUT** (only `libtakum` C99) | no silicon/FPGA; log datapath is heavy; adoption ≈0 |
| **OCP MX (MXFP4/8/6)** | 2023 | block-shared E8M0 exponent per k=32 | ASIC tensor cores (Blackwell), **not an LUT axis** | block-granularity scale; not a standalone scalar type; FPGA-hostile heterogeneous datapath |
| **NVIDIA FP8** (E4M3/E5M2) | 2022 | two 8-bit encodings (fwd/bwd) | H100 tensor cores (ASIC); on FPGA, mul is still costly (IEEE Xplore 11008970) | dual-encoding doubles toolchain; E4M3 trades range, E5M2 trades precision |
| **bfloat16/8** | 2017 (Google) | FP32 exponent + truncated mantissa | trivial convert to FP32, **minimal custom logic** | a dumb range-cut; low precision near ±1 (wastes bits without a taper) |

**Positioning:** competitors split into *(a) ASIC-tuned block formats* (MX, FP8,
BF16 — low LUT relevance) and *(b) tapered scalar formats* (Posit, Takum — high
LUT cost, weak FPGA evidence). **Trinity-GF's opening = fixed-width taper +
bit-exact decode + `1.63·W²` LUT target** — unaddressed by either camp.

## 2. The main FPGA rival — Posit

Posit32 on FPGA = **2–4× IEEE FP32 LUT** for add/mul (FP32 mul maps to DSP, posit
does not). This is the direct comparison: Trinity-GF claims a **sub-posit** ADD
target (`1.63·W²`). For the paper to be convincing, GF16/GF24 ADD/MUL LUT must be
compared **on the same toolchain (openXC7/yosys), at the same bit-exactness**,
against posit16/posit24 ADD/MUL LUT, and the gap shown. This is **experiment #1
of the missing proof** (see article-strengthening options).

> Caveat found during this audit (see `PAPER_INTEGRITY_ISSUES.md` §E1): the repo
> has **no native posit add/mul core** — the `corona_compute_posit16_mul` cell is a
> binary32 proxy (`gf_mul_param` E8M23). A fair GF-vs-posit LUT head-to-head
> therefore requires porting a real posit multiplier first.

## 3. Takum — the "out-publish" priority

Takum (2024) is the only competitor that:
- directly criticizes Posit for the dynamic-range collapse (as Trinity does),
- BUT has **no** FPGA/LUT evidence at all.

Trinity-GF already has decode-RTL + bit-exact witnesses — what takum lacks.
=> Strategy: contrast explicitly in Related Work ("takum solves the same
range problem but without hardware evidence; we provide bit-exact decode on
3 witnesses + an LUT floor"). A strong differentiator for a reviewer.

## 4. Supporting literature (justifies the LUT axis)

- **LUTMUL** (FPGA 2025, ACM 10.1145/3658617.3697687): LUTs on FPGA outnumber DSPs
  ~100× → LUT-native multipliers beat the DSP roofline. **Justifies choosing LUT as
  the primary metric for Trinity-GF.**
- **8-bit Transformer inference on edge** (Yu/Prabhu): posit8 and FP8 both reach
  BF16 accuracy at lower area/power.
- **FPGA Approximate Multiplier for FP8** (IEEE Xplore 11008970, 2024): dense FP8
  mul is costly on FPGA → approximations are needed — validates that GF addresses a
  real pain point.

## 5. Honest caveats for the paper (from the repo audit)

These must either be closed by an experiment or explicitly disclosed — otherwise a
reviewer will find them:

1. **All LUT numbers are yosys pre-P&R**; there is no committed nextpnr `.rpt`.
   This is already disclosed in Threats to Validity (`paper.tex:1236`), but it can
   be strengthened with one nextpnr run (option B).
2. **GF64 is NOT bit-exact on silicon** (359/512 = 70.1%, `paper.tex:378`). The
   abstract says "Ten GoldenFloat formats … 0 failures on silicon" — this must be
   explicitly bounded to "bit-exact for formats ≤ GF32"; GF64 called "best-effort".
   (Verified: the abstract does correctly say "GF4–GF32", so GF64 is excluded —
   this is fine as written.)
3. **Samples of 64–512 vectors on silicon** are small. The abstract can read as
   exhaustive; clarify "representative sweep, 64–512 samples" in §Methodology.
4. **takum16 MUL = 505 LUT is claimed in `paper.tex:337`** — the RTL artifact
   `takum16_native_mul.v` DOES exist (verified), but the committed 505 figure needs
   a committed yosys `.rpt` to be reproducible (see `PAPER_INTEGRITY_ISSUES.md` §E2
   on LUT reproducibility fragility).

Full list of paper contradictions: `research/PAPER_INTEGRITY_ISSUES.md`.
