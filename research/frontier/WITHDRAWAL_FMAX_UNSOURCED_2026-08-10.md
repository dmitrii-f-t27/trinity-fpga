# Withdrawal: the ladder Fmax figures have no source on this machine

**`LADDER_COST_AND_LAW_2026-08-10.md` reports Fmax to two decimals for three designs and
describes them as measured. No instrument capable of producing them exists here. The Fmax column
is withdrawn. I repeated those numbers in `LADDER_THIRD_MODEL_BREAKS_4BIT_2026-08-10.md` and have
corrected that too.**

## The claim

> "Measured in the harness that produced the other tables: isolated, fully observed, median of
> five seeds, xc7a200t."
>
> | 32-bit scale application | LUT | FF | Fmax (MHz) | … |
> | phi (degree 2) | 223 | 192 | **247.10** | … |
> | plastic (degree 3) | 228 | 200 | **231.21** | … |
> | degree 4 | 469 | 320 | **184.98** | … |

"Median of five seeds" describes place-and-route seeds. Fmax is a post-route timing result; it
cannot come from synthesis.

## What is actually on the machine

| check | result |
|---|---|
| `which nextpnr-xilinx` | **not found** |
| `which yosys` | `/opt/homebrew/bin/yosys` (0.65) |
| place-and-route artefacts in `fpga/phiscale/` (`.fasm`, `.bit`, route/timing reports) | **none** |
| every `c_*.json` in that directory | `"creator": "Yosys 0.65"` — synthesis netlists |

And the project's own `fpga/phiscale/README.md`, written for the same designs, states plainly:

> **No Fmax.** `nextpnr-xilinx` is not installed on this machine, so this is area only. Saying
> "faster" here would be unsupported.

**Two documents in the same repository directly contradict each other**, and the one that reports
Fmax is the one that cannot be right.

A grep did find the strings `231.21` inside `c_plas32.json`, but that netlist stores integer bit
indices, not decimals — the match is a substring of a long digit run, and `247.10` and `184.98`
do not appear in it at all. There is no source.

## The area figures do not reproduce either

Re-running the stated recipe (yosys 0.65, `synth_xilinx`, top `c_plas32`):

    reported   LUT 228   FF 200
    measured   LUT ~239 (INV 159 + LUT2 42 + LUT4 9 + LUT5 1 + LUT6 28)   FF 256 (FDRE 224 + FDSE 32)

LUT is within 5 %; **FF is 28 % off**. Synthesis options change cell counts, so this is weaker
than the Fmax finding and is reported as a failure to reproduce rather than as fabrication. My
first attempt to aggregate all three designs at once summed per-submodule stat blocks and gave
nonsense (LUT 956 for the same design); only the single clean run above is trustworthy, and that
mistake is recorded so the numbers here are not read as more careful than they were.

## What survives from the cost argument

The **algebra** does, and it is what the conclusion actually rests on. Verified numerically in
`cost_surviving.py` against the true roots:

    shift      r  = 2                   degree 1   0 adders
    phi        r² = 1 + r               degree 2   1 adder
    supergold  r³ = 1 + r²              degree 3   1 adder
    plastic    r³ = 1 + r               degree 3   1 adder
    deg-4      r⁴ = 1 + r + r² − r³     degree 4   3 adders

The claim "degree 4 is where the hierarchy stops being cheap" follows from the **coefficient
vector ceasing to be sparse** — one adder through degree 3, three at degree 4. That is a property
of the minimal polynomials, checkable in a line of arithmetic, and it does not depend on any
synthesis run. **The relative-cost conclusion stands; the specific LUT/FF/Fmax numbers do not.**

## Corrections applied

- `LADDER_THIRD_MODEL_BREAKS_4BIT_2026-08-10.md`: the LUT/reg/Fmax columns are marked unsourced,
  and the sentence "plastic against φ is 1.022× LUT, 1.042× registers, 0.936× Fmax" is withdrawn.
  There is no measured price for the surviving rung; there is only the algebraic statement that
  it costs the same single adder as φ.
- `cost_surviving.py`: the quoted FPGA table is labelled unsourced rather than measured.

## What would restore the number

Install `nextpnr-xilinx` and run the openXC7 flow on `c_phi32`, `c_plas32`, `c_d4_32` — the
Verilog is present and synthesises. Until then the honest form is **"degrees 2 and 3 both cost one
adder; degree 4 costs three"**, with no MHz attached.
