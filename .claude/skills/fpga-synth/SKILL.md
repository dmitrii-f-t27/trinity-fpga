---
name: fpga-synth
description: "AX7203 openXC7. 72 format oracles. 10 GF bit-exact. Paper PDF compiled. arXiv-ready."
allowed-tools: Bash(docker *), Bash(ls *), Read, Grep, Glob, Write, Edit
---

# FPGA Pipeline — AX7203 XC7A200T

## Current State (2026-07-14, Wave 13 — PDF compiled, paper submittable)

| Axis | Count | Detail |
|------|-------|--------|
| SW-bitexact | ~62-69/83 | (CATALOG_MATRIX: strict 62, self-consistent 69) |
| decode-HW Tier-E | 41 formats | 41 unique formats with bit-exact decode cells |
| compute-HW Tier-E | 10 GF formats × {ADD,MUL} | GF4-GF32 (10 formats), 0 failures on silicon (vectors vary by run) |
| GF64 ADD | 70.1% (359/512) | timing closure failure; clamp reverted (regressed to 48.9%) |
| DIV/SQRT | binary32 proxy | NOT native GF, stale output bug, no conformance |
| QUIRE | untested | no conformance vectors |

**Honest catalog**: 10 formats bit-exact (add/mul) + 2 proxy (div/sqrt) + 1 untested (quire)
**Paper**: ~41/83 formats (NOT 71 — that was cell count, not format count)

## Synthesis Flags (MEASURED, not assumed)

| Design type | Flags | Notes |
|-------------|-------|-------|
| ADD/SUB | `-flatten -abc9 -nocarry -arch xc7` | -abc9 REQUIRED (removal = 70%→19%) |
| MUL | `-flatten -abc9 -nocarry -nodsp -arch xc7` | -nodsp for MUL only |
| GF16 MUL | uses 1 DSP48E1 | explicitly instantiated, not inferred |

LUT measurements (yosys 0.63, -abc9 -nocarry):
- GF16 parametric adder: 486 LUT
- GF16 old adder: 176 LUT (BENCH-005 "118" was stale)
- tekum16 stub: 573 LUT
- takum16: N/A (RTL doesn't exist)

## Build Recipe

```
docker run --rm regymm ... bash -c '
  yosys -p "read_verilog gf_adder_param.v ${DESIGN}.v; synth_xilinx -flatten -abc9 -nocarry -arch xc7; write_json ${DESIGN}.json"
  nextpnr-xilinx --chipdb /chipdb-xc7a200tfbg484-2.bin ...
  fasm2frames ... && xc7frames2bit ...
'
```

## GF64 Root Cause (Waves 3-8)

**NOT a logic bug** — iverilog 6/6 + Python 1544/1544 ALL_PASS.
**IS a timing closure failure** — 43-bit barrel shifter + 64-bit priority encoder too deep for CFGMCLK.

Timeline:
- Wave 3: root cause found (timing, not logic)
- Wave 4: clamp attempted → -0+0 fixed but overall regressed 70→49%
- Wave 8: clamp REVERTED → HEAD reproduces 70.1%
- Future: 2-stage pipeline is definitive fix

## LESSONS (Waves 1-8, auditor-verified)

1. HAS_INF per-format (only GF16)
2. cur_byte must be reg
3. iverilog is fast gate
4. Provenance before every flash
5. Trinity moat = catalog × open-source-silicon proof
6. Tekum = nearest competitor (GF16 0.85x LUT, not 4-11x)
7. DePIN + openXC7 = strongest niche
8. TX NBA race: use buffer+mux
9. -abc9 REQUIRED (removal = catastrophic regression)
10. GF64 timing: barrel shifter + priority encoder, pipeline needed
11. ELiTeFormer + MxGLUT validate zero-DSP thesis
12. **"4-11x lower LUT" is FALSE** — measured 0.85x
13. BENCH-005 "118 LUT" is stale — same module gives 176
14. takum16 adder RTL does NOT EXIST
15. **div/sqrt = binary32 proxy** — NOT native, hardcoded, stale output
16. **gf_mul_param same timing risk** as adder for GF64+
17. **"71/83 formats" was wrong** — double-counted cells as formats (real: ~41)
18. **"-nodsp mandatory" was wrong** — only MUL uses -nodsp, ADD doesn't
19. **Clamp regressed** — reverted to make HEAD reproducible at 70.1%
20. **build-matrix.yml was dead code** — both if/else branches identical, now fixed
21. **"11392/11392" was FABRICATED** — table sums to 11976, GF16 log shows 512 not 128, no artifact contains it. Replaced with honest per-cell summary.
22. **LUT wrapper committed** — gf16_param_top.v in repo, reproducible from clean clone (491 LUT with -flatten)
23. **LaTeX skeleton created** — paper.tex exists but full conversion still needed for arXiv
24. **27-agent system is vapor** — only self.json exists, verdict.zig missing, tri CLI not built
25. **72 formats have oracle** — 10 new oracle files (posit, bf16, fp8, mxfp, takum, decimal, ieee, legacy, lns, int)
26. **1496 TX race wrappers fixed** — auto-script converted all to buffer+mux
27. **2-stage pipeline implemented but REGRESSED** — iverilog 9/9 but silicon 50.6% (worse than 70.1%). Reverted.
28. **GF64 ceiling = 70.1%** on AX7203/CFGMCLK — no RTL modification improves on original. External clock = only untested approach.
29. **Full LaTeX paper** — 648 lines, 3888 words, research/arxiv_submission/paper.tex
30. **Paper PDF compiled** — 314KB via CI (build-paper.yml), arXiv-submittable
31. **All 12 oracles have self-tests** — gf_ref.py was the last (added Wave 13)
32. **Paper structural count reconciled** — ~10 structural + 2 routing-pending + 3 single-witness = 15
33. **takum64 routing claim was FALSE** — CI failed all 8 seeds, paper fixed to ✗
34. **`make oracle/repro/bench/lut`** — reproducibility from clean clone, no hardware needed
35. **#199 body updated** — honest ~49-55/83 (was stale 71/83 double-count)
36. **Paper is fully honest** — zero known falsehoods remaining
37. **72/72 formats have conformance vectors** — 791,115 vectors via `make vectors`
38. **`make vectors`** — generates JSON vectors for all 72 oracle formats from clean clone
39. **MUL vectors generated** — 72 ADD + 72 MUL = 144 files, 1,559,190 total vectors
40. **Honest catalog coverage = 72/83 THEORETICAL MAX** — 15 oracle modules, 84 format names. Remaining 11 are structural (no decode law). Zero concrete gaps.
41. **SUB vectors generated** — 287 total JSON files (ADD+MUL+SUB), 2,426,879 vectors
42. **61 CI workflows** (was 3388 → 102 → 61). 41 orphan May-era workflows deleted.
43. **arXiv submission checklist** — ALL items checked except "Upload" (user action)
44. **Paper 1 (2606.05017) needs v4**: add GF64 ceiling, takum comparison, FL-002 update
45. **Paper 2 (2606.09686) needs v3**: add 72-oracle suite, reproducibility, replace φ-anchor
46. **Zero citations on both papers** — 3-6 weeks old, no community uptake
47. **Biggest competitor**: Hunhold takum (2404.18603 + FPGA codec 2408.10594)
48. **EXISTENTIAL risk**: OCP-MX (9 citations, silicon shipping) + IEEE P3109 (standards-track)
