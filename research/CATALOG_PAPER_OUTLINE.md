# Paper Outline — 83-Format openXC7 Catalog Benchmark

**Working title:** *83 Number Formats on Open-Source Silicon: A Reproducible Benchmark of Decode and Compute on openXC7*
**Author:** Dmitrii Vasilev (ORCID 0009-0008-4294-6159)
**Target:** arXiv **cs.AR** (Hardware Architecture); secondary cs.ET
**Status:** Outline, pre-draft. All counts sourced from EPIC gHashTag/trinity-fpga#199; re-verify every number against the live SSOT before submission.
**Scope rule (honesty):** This paper does *not* introduce a new number format and makes no superiority claim over posit, takum, or microscaling formats. Its contribution is the *breadth of formats proven on vendor-neutral silicon* plus the *open toolchain methodology*.

---

## Key claims (honest, verifiable)

1. **71 of 83 catalog formats carry at least one bit-exact silicon cell** on a Xilinx Artix-7 (XC7A200T, ALINX AX7203) via a fully open toolchain (openXC7: Yosys + nextpnr-xilinx + Project X-Ray). Breakdown: 41 decode ports + 30 compute cells. Each cell ships a full evidence chain: CI build → bitstream SHA-256 → JTAG flash → UART verify against an independent exact-arithmetic oracle.
2. **16 GoldenFloat compute cells** (GF4–GF32, ADD and MUL) verify bit-exactly on the same fabric. *Author note: reconcile 7 widths × 2 ops = 14 vs the stated 16 against EPIC #199 before submission.*
3. **Four parameterized decode templates** cover the decodable catalog: (a) algebraic, (b) table-2^x, (c) transcendental-exp-via-tables, (d) truncated-multiply. This is the citable methodological artifact.
4. **LUT-only constraint (zero DSP).** Project X-Ray documents the Artix-7 DSP48E1 hard block as only *partially* reverse-engineered; all designs therefore synthesize with `synth_xilinx -nodsp`. This is an open-toolchain limitation, not a design choice, and is reported as such.

### Explicitly NOT claimed

- No "first," "best," "only," or "novel format" language. The formats are an *existing* catalog [arXiv:2606.09686, erratum of 84].
- No claim that the φ-ratio selection rule yields superior accuracy; it is treated as a *design heuristic* within the catalog, consistent with the literature-scan finding that the optimal exponent/mantissa split depends on workload, not a universal constant [arXiv:2208.09225].
- No competitive ML-throughput claim. The openXC7 flow targets small designs; scaling to full attention blocks is unproven.
- No claim that LUT-only is preferable to DSP; it is a *constraint imposed by the toolchain*.

---

## Abstract (draft, ~200 words)

We present a reproducible hardware benchmark of 83 numeric formats spanning 13 families — including IEEE-754 fp8/fp16/bfloat16, OCP MXFP4/8 elements, posit, takum, logarithmic, decimal, and the φ-derived GoldenFloat family — implemented on a Xilinx Artix-7 (XC7A200T) using a fully open toolchain (openXC7: Yosis + nextpnr-xilinx + Project X-Ray). 71 of 83 formats carry at least one bit-exact silicon cell against an independent exact-arithmetic oracle, reached through four parameterized decode templates (algebraic, table-2^x, transcendental-exp-via-tables, truncated-multiply). 16 GoldenFloat compute cells (GF4–GF32, ADD and MUL) verify bit-exactly on the same fabric. Because Project X-Ray documents the DSP48E1 hard block as only partially reverse-engineered, every design is synthesized LUT-only (`synth_xilinx -nodsp`); we therefore report LUT counts and place-and-route yields per cell, including the openXC7-specific result that wide carry-chain multiplies fail routing while wide BRAM tables route successfully (decimal128 routes at 336 bits; an untruncated 140-bit takum multiply fails across 32 seeds). The contribution is not a new format and claims no superiority over posit, takum, or microscaling designs; it is the breadth of formats proven on vendor-neutral silicon, together with the open toolchain methodology and a per-cell reproducible evidence chain.

---

## 1. Introduction

- Motivation: low-precision numeric formats are proliferating (FP8, MXFP, posit, takum, minifloat), yet published hardware numbers are almost always produced on *closed* vendor flows (Vivado, ASIC PDKs). Independent, reproducible, vendor-neutral silicon evidence is scarce.
- Contribution statement (three parts): (i) a breadth benchmark — 83 formats, 71 with bit-exact silicon cells; (ii) a methodology — four decode templates + a truncation-analysis sweep that makes "does format X route on openXC7?" a one-command question; (iii) a toolchain-finding — the LUT-only constraint and the wide-multiply-vs-wide-table routing asymmetry.
- Why this matters: positions the work as an *independent proving ground* for formats whose authors (e.g., takum [arXiv:2404.18603]) publish the encoding but not open-silicon numbers.
- Non-goals, stated up front (mirrors the honesty rule above).

## 2. Background — the number-format landscape

- IEEE-754 lineage and the minifloat revival (FP8 E4M3/E5M2 [arXiv:2209.05433]).
- Tapered precision: posit → takum [arXiv:2404.18603] → tekum [arXiv:2512.10964]. Note that tapered designs are *structurally different* from the linear S:E:M family; Trinity's catalog includes both but does not merge them.
- Block-scaled microscaling (OCP MX [arXiv:2310.10537], NxFP [arXiv:2412.19821], MX+ [arXiv:2510.14557]).
- First-principles floats: AetherFloat [arXiv:2603.08741].
- The φ-derived GoldenFloat family [arXiv:2606.05017] as one *member* of the catalog — encoding is conventional IEEE-754-style linear; the only distinguishing rule is the exp/mant → 1/φ selection heuristic.
- The 83-format / 13-family catalog [arXiv:2606.09686, erratum correcting an earlier count of 84; E8M0 is a shared-exponent component of Microscaling, not a standalone row].

## 3. Methodology

### 3.1 The openXC7 flow
- Toolchain: `regymm/openxc7` Docker (Yosys + nextpnr-xilinx + Project X-Ray). Target: ALINX AX7203, `xc7a200tfbg484-2`, IDCODE `0x13636093`.
- The LUT-only constraint: `synth_xilinx -nodsp` is mandatory because DSP48E1 inference breaks routing on this part under the open flow; Project X-Ray documents DSP as "Partial." State this as a *toolchain limitation*, not a feature.
- Placer note: `--placer heap` strictly dominates `sa` for wide datapaths (empirical, GF20 case study).
- Clock: CFGMCLK via STARTUPE2 (~69–70 MHz, measured).

### 3.2 Evidence chain (per Tier-E cell)
```
.tri/.v RTL → openXC7 CI synth → bitstream (.bit) + SHA-256
           → JTAG flash (openocd) → UART verify vs independent golden oracle
```
- Independent oracle: exact rational arithmetic (`fractions.Fraction`), deliberately distinct in implementation from the DUT-derived reference testbench. This separation is what lets silicon catch "bug-equals-bug" defects (GF16 NaN case study).

### 3.3 Four decode templates
1. **Algebraic** — single table lookup + integer multiply (e.g., decimal32/64/128: C × 10^de). Routes at 336-bit width.
2. **table-2^x** — exponent field + small power-of-two table.
3. **Transcendental-exp-via-tables** — decompose exp(ell/2) → 2^L, range-reduce L = k + frac, compute 2^k via the FP32 exponent field and 2^frac via a 65 536-entry BRAM table + Taylor correction (takum [arXiv:2404.18603]).
4. **Truncated-multiply** — Mitchinson–Smith sticky-OR truncation to bring wide carry-chain products below the openXC7 routing ceiling (takum64: 119+140-bit → 94+72-bit, bit-exact).

### 3.4 Tier definitions
- **Tier E** (silicon): CI run + bitstream SHA-256 + UART log published.
- **Tier C** (self-report only): zero remaining in this benchmark.
- The honest ceiling: of 83 formats, 62 are software-bit-exact fixed-layout S:E:M; 15 are *structural by design* (parametric, non-S:E:M, block-scaled) and are not "gaps to close."

## 4. Results

### 4.1 Tier-E matrix
- Headline: **71/83** formats carry ≥1 bit-exact silicon cell (41 decode + 30 compute). *Table: per-family coverage (GF, IEEE, MX, posit, takum, decimal, LNS, …).*
- Decode coverage highlights: binary16 exhaustively verified (65 536/65 536); fp8_e4m3/e5m2, posit8, lns8, int4/int8 at 256/256; bf16/nf4/fp4/fp6 at full corner coverage.
- Compute coverage: GF4–GF32 ADD and MUL bit-exact on silicon; SUB correct by reduction to the silicon-proven ADD core.

### 4.2 LUT counts
- LUT-only MAC numbers, with **PERI [arXiv:1908.01466]** (3507 LUTs, 100 MHz on the identical Artix-7-100T) as the canonical posit baseline.
- GoldenFloat GF16 adder: **294 LUTs** [confirm against EPIC #199]. *Author: fill the full per-format LUT table here.*

### 4.3 Route yields
- The openXC7 routing asymmetry: **wide tables route, wide multiplies do not.**
- takum64 routing unlock: untruncated 119-bit and 140-bit products fail across 32 seeds; sticky-OR truncation to 94+72-bit routes and is *strictly more correct* (2 fails vs 5 on a 4 848-vector stress set, zero regressions).
- decimal128 (336-bit datapath) routes — because its wide signal is a table, not a carry-chain multiply.

### 4.4 Two case studies where silicon caught what simulation hid
- GF16 NaN propagation ("bug-equals-bug"): the reference testbench shared the design's blind spot; only the independent golden exposed Inf-instead-of-NaN. Fix verified 512/512 on silicon.
- GF20 place-and-route: 9× misdiagnosed as "Docker Hub hang"; per-step CI timing proved the real blocker was nextpnr `--placer sa`; switching to `heap` routed in ~8 s.

## 5. Related work

| Cluster | Reference | Relation |
|---|---|---|
| Tapered precision (takum) | Hunhold, *Beating Posits at Their Own Game: Takum Arithmetic*, CoNGA 2024, [arXiv:2404.18603](https://arxiv.org/abs/2404.18603) | Defines takum; Trinity's catalog independently proves takum decode on open silicon. |
| Ternary tapered precision (tekum) | Hunhold, *Tekum: Balanced Ternary Tapered Precision Real Arithmetic*, [arXiv:2512.10964](https://arxiv.org/abs/2512.10964) | Tapered precision for balanced ternary; occupies the ternary+float intersection. Adjacent, not a baseline here (no codec published). |
| Posit on identical board | Tiwari et al., *PERI: A Posit Enabled RISC-V Core*, [arXiv:1908.01466](https://arxiv.org/abs/1908.01466) | Posit FPU on Artix-7-100T (3507 LUTs, 100 MHz). Canonical LUT baseline for this board. |
| FPGA minifloat MAC | Aggarwal et al., *Shedding the Bits: Minifloats on FPGAs*, FPL 2024, [arXiv:2311.12359](https://arxiv.org/abs/2311.12359) | Parameterized FP3–FP8 FPGA MAC; closest prior art to Trinity's parameterized GF MAC. |
| First-principles float | Morisaki, *AetherFloat*, [arXiv:2603.08741](https://arxiv.org/abs/2603.08741) | Quad-radix float with VLSI area/power/delay numbers Trinity does not have; sets the bar for any silicon-area claim. |
| Takum FPGA codec (companion) | Hunhold, *Takum Hardware Codec*, [arXiv:2408.10594](https://arxiv.org/abs/2408.10594) | VHDL takum codec: −38% latency, −50% LUT vs posits. The comparison point for any takum-on-FPGA number. Closed-flow. |
| OCP microscaling | Rouhani et al., *Microscaling Data Formats for Deep Learning*, [arXiv:2310.10537](https://arxiv.org/abs/2310.10537) | Defines MX; Trinity's catalog includes MXFP4/8 elements. |

Position this paper as **complementary**, not competitive: Hunhold publishes formats and (for takum) a closed-flow codec; PERI and Aggarwal publish single-family FPGA numbers on closed flows; this work contributes *breadth on an open flow*.

## 6. Discussion — limitations of openXC7

- **DSP partial.** The zero-DSP constraint caps achievable GFLOPS and is a toolchain artifact. If Project X-Ray completes DSP48E1 documentation, the MAC designs should port to DSP; the LUT-only numbers are a *lower bound on effort*, not an upper bound on performance.
- **BRAM partial.** Constrained BRAM inference; the benchmark uses explicit 65 536-entry tables rather than inferred block RAM.
- **Scaling.** 100% synth success is on *small* designs (decode ports, single MACs). Scaling to full attention blocks or large matmuls on Artix-7 under openXC7 is unproven; Vivado remains far superior for large designs.
- **Bit-for-bit reproducibility** of the open flow is the trust anchor for any downstream DePIN/attestation use; reproducible-builds discipline is required and not yet formally certified.
- **Structural formats.** 15 of 83 are structural-by-design (parametric, block-scaled, non-S:E:M) and are honestly reported as such rather than forced into bit-exact boxes.

## 7. Conclusion

- Restate the three contributions without superlatives: breadth (71/83 silicon cells), methodology (4 templates + truncation sweep), toolchain finding (LUT-only, wide-multiply routing asymmetry).
- Future work: port MAC to DSP when Project X-Ray completes it; add tekum [arXiv:2512.10964] to the catalog and benchmark head-to-head; formalize reproducible-builds attestation for DePIN.
- Closing line: an open, vendor-neutral proving ground for the proliferating low-precision-format space.

---

## Submission checklist (author)

- [ ] Re-verify 71/83, 41 decode + 30 compute, 16 GF compute cells against live EPIC #199 (note 7 widths × 2 ops = 14 ≠ 16).
- [ ] Fill per-family Tier-E table (§4.1) and per-format LUT table (§4.2) from EPIC #199.
- [ ] Confirm GF16 = 294 LUT and add PERI 3507-LUT comparison.
- [ ] Add figures: (a) evidence-chain pipeline diagram, (b) GF4–GF32 ladder, (c) decode-template taxonomy, (d) wide-multiply-vs-wide-table routing result.
- [ ] Target venues: ISFPGA 2026 / ARITH 2026 (in addition to arXiv cs.AR).
- [ ] Erratum dependency: catalog paper [arXiv:2606.09686] v1 says 84; v2 corrects to 83. Cite the corrected count and footnote the E8M0 reasoning.
