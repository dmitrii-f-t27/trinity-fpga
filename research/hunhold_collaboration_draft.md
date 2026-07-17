# Draft: Collaboration Email to Jasmin Hünhold (takum author)

**Subject:** Independent FPGA LUT measurement of takum16 multiply — 505 LUT equivalence with GF16

---

Dear Jasmin,

I am a researcher working on low-precision floating-point formats for LLM training on FPGA. I have been following your work on takum and tekum with great interest.

During our open-source FPGA synthesis experiments (Xilinx Artix-7 XC7A200T, Yosys 0.63 + ABC9, zero-DSP mode), we measured the LUT cost of a native takum16 logarithmic multiply at **505 LUT** — identical to our GoldenFloat16 (IEEE-style 1S+5E+10M) multiply, which also measured 505 LUT.

This equivalence suggests that on LUT6 architectures in the zero-DSP regime, the multiply cost converges to approximately 2W² regardless of the encoding (linear FP vs. logarithmic). We call this the "Encoding Equivalence" observation. Your takum codec paper (arXiv:2408.10594) reports similar LUT reductions vs. posits, which is consistent with our finding.

I would be interested in collaborating on a joint paper formalizing this "encoding invariance" — specifically:

1. Measuring takum multiply LUT across multiple widths (8, 16, 32) on the same FPGA toolchain
2. Comparing with IEEE-style and GoldenFloat formats at matched widths
3. Investigating whether the convergence to 2W² is a theoretical floor or toolchain-specific

Our measurements are available with full Yosys CI reproducibility at:
https://github.com/gHashTag/trinity-fpga (research/CI_LUT_REPORT.md)

Note: These are pre-place-and-route Yosys synthesis estimates. Post-P&R LUT counts are typically 15-30% higher. We are working on adding nextpnr utilization reports for full reproducibility.

I look forward to hearing your thoughts.

Best regards,
Dmitrii Vasilev
ORCID: 0009-0008-4294-6159
