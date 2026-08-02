# Is the ternary node portable IP, or is it a 7-series design?

Measured 2026-08-02. This document exists to settle one question, and it was
written to be capable of returning the answer nobody wanted.

Option C in the 2026-08-02 report proposed selling the balanced-ternary MAC cell
as portable soft IP. The review attached a falsifier to it:

> Second falsifier: attempt to port the cell to a non-Xilinx target and measure
> how much of it is 7-series-specific. If most of it is, there is no IP to sell.

The review expected that to kill option C. Its stated reasoning was that "LUT
counts tuned to a 7-series carry chain are not portable IP; the deliverable would
be rebuilt, not repackaged." That was a reasonable prediction. It was wrong, and
the way it was wrong is more interesting than a pass would have been.

---

## What was done

`fpga/vivado/trinet_node_v2_ax7203.v` was split. Everything Xilinx moved into a
board wrapper; everything else became `fpga/portable/trinet_node_core.v`. The
audit of what actually had to move found exactly two primitives:

| primitive | what it supplied | what replaced it |
|---|---|---|
| `STARTUPE2` | CFGMCLK, the configuration oscillator used as system clock | `clk` input |
| `DNA_PORT` | factory device identity | `node_id` input |

Nothing else in the cell was vendor-bound. Not the UART, not the frame parser,
not the dot product, not the SipHash engine.

The core was then run through every `synth_<family>` pass yosys 0.63 offers.
Ten completed. **The wrapper still instantiates the core rather than keeping a
copy** — a parallel copy would drift, and the portability claim would quietly
stop being true while both files still built.

---

## Result

| family | vendor | total cells | LUTs | **flip-flops** | multipliers |
|---|---|---|---|---|---|
| xilinx (xc7, flattened) | AMD | 2830 | 1737 | **819** | **0** |
| ice40 | Lattice | 2568 | 1459 | **819** | **0** |
| ecp5 | Lattice | 2488 | 1286 | **819** | **0** |
| nexus | Lattice | 2083 | 939 | **819** | **0** |
| gowin | Gowin | 2842 | 1663 | **819** | **0** |
| gatemate | Cologne Chip | 2357 | 1180 | **819** | **0** |
| anlogic | Anlogic | 2223 | 1059 | **819** | **0** |
| efinix | Efinix | 2352 | 1187 | **819** | **0** |
| nanoxplore | NanoXplore | 2120 | 1178 | **819** | **0** |
| intel_alm | Intel/Altera | 2288 | 1267 | 831 | **0** |

Ten families, eight vendors. Zero synthesis errors. Zero inferred multipliers
anywhere. (`achronix` and `easic` also exist as passes but need a device
argument to run, so they were skipped rather than counted as failures.)

**The number that matters is the flip-flop column.** 819 registers on nine of
ten families, and 831 on the tenth — Intel's ALM absorbs some reset logic into
the register cell, which accounts for the twelve. Ten independent synthesisers,
written against ten different architectures, agreed to the register on how much
sequential state this design has.

That is not a coincidence and it is not a good result achieved by tuning. It is
what happens when a design is expressed in ordinary RTL rather than in vendor
idioms: the sequential structure is a property of the design, and every tool
recovers it exactly. The combinational column varies from 939 to 1737 LUTs, a
1.85× spread, and that variation is entirely explained by LUT width and carry
architecture — Lattice Nexus packs into 939 wide LUTs what iCE40 needs 1459
LUT4s to express. That is the mapper doing its job, not the design failing to
port.

This is now checked rather than remembered. `conformance/portability_check.py`
re-runs every family yosys offers and asserts the *invariant* — that the
sequential state agrees across families and that nobody infers a multiplier —
rather than asserting the numbers in the table above. Asserting the numbers
would fail on a yosys upgrade for no reason; asserting the invariant fails only
when the design has actually acquired a vendor dependency. Both of its
assertions were confirmed to fire: tightening the tolerance to 5 makes it
reject the real Intel spread, and demanding 20 families makes it refuse to
pass on 10.

---

## What this does and does not establish

**Established.** The cell contains no vendor-specific arithmetic. The claim
"0 DSP" is not a Xilinx artifact of `-nodsp`; nine other toolchains, given no
such flag, also declined to infer a multiplier, because `popcount(agreements) −
popcount(disagreements)` contains no multiply to find. The design synthesises
clean on every family tried, first attempt, with no per-family conditionals.

**Not established.** Synthesis is not place-and-route. None of these mappings
has been through a P&R tool or met timing, and locally only
`nextpnr-himbaechel` is installed — no `nextpnr-ice40`, no `nextpnr-ecp5`, no
`icepack`, no `ecppack` — so P&R on non-Xilinx families could not be attempted
here. Only the xc7 path has produced a bitstream, and only the xc7 path has run
on silicon. A design that synthesises everywhere can still fail timing
somewhere, and until that is measured this is portability of *source*, not
portability of *product*.

**Also not established, and worth saying plainly:** portable does not mean
wanted. This measurement answers whether the cell *could* be sold as IP. It says
nothing about whether anyone would buy it, and the report's other objections to
option C — no measured power, no device-bound identity, no fab path — are
untouched by anything here. A radiation-hardened programme office does not care
that a design compiles for Gowin.

---

## What the measurement changed

Option C's cost line said the deliverable "would be rebuilt, not repackaged".
That specific objection is now falsified: the deliverable is one 272-line file
that builds on ten families unmodified. The *effort* estimate for option C
drops substantially, because the portable artifact turned out to already exist
inside the board design and needed extraction, not a rewrite.

The other objections to option C stand, and they were always the stronger ones.
The recommendation "C not this year" does not change on this evidence. What
changes is that the reason is now honestly about market access rather than about
engineering, and that is a better reason to have.

---

## A defect this work surfaced

Splitting the file required re-running `formal/trinet_node_v2_tb.v`, which
failed 0/6 — and failed identically on the pre-split design, which is what
proved the split behaviour-preserving. Tags matched bit-for-bit between the two
versions at every vector.

The failure was older and separate. The testbench did not pass a key; it relied
on the module's default. When W01 replaced the compromised default key with a
null one, the golden tags in the testbench silently stopped matching anything
the RTL could produce, and the test had been asserting against a key that no
longer existed. Fixed by passing the canonical SipHash-2-4 reference key
explicitly, with the golden values regenerated from the independent Python
implementation rather than from the RTL — 6/6.

**A test that depends on a default is a test that stops testing the moment the
default is corrected.** The security fix broke the test that guarded the
security property, and nothing said so.

---

## Reproducing

```bash
yosys -p 'read_verilog fpga/portable/trinet_node_core.v fpga/openxc7-synth/trinet_siphash24.v; hierarchy -top trinet_node_core; synth_ecp5 -top trinet_node_core; stat'
```

Substitute any of `synth_ice40`, `synth_gowin`, `synth_gatemate`, `synth_nexus`,
`synth_intel_alm`, `synth_anlogic`, `synth_efinix`, `synth_nanoxplore`. For
Xilinx, add `-flatten -nocarry -nodsp -arch xc7`.

All of them at once, with the invariant checked:

```bash
python3 conformance/portability_check.py
```

Equivalence of the split:

```bash
iverilog -g2012 -o /tmp/v2.vvp formal/trinet_node_v2_tb.v fpga/vivado/trinet_node_v2_ax7203.v fpga/portable/trinet_node_core.v fpga/openxc7-synth/trinet_siphash24.v && vvp /tmp/v2.vvp
```

---

Author: Dmitrii Vasilev ([@gHashTag](https://github.com/gHashTag))
