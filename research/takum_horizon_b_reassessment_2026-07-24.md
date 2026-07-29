# takum class: reconsidering horizon B (loop 24.07.2026)

> Status tags: `[proven]` / `[measured]` / `[verified SW on iverilog]` /
> `[open hypothesis]` / `[REQUIRES USER ACTION]`.
> Everything is cross-checked against live sources (public GitHub API + local clone), NOT from memory.

## Main honesty correction (BINDING)

The previous diagnosis (recipe-takum-research, completion-strategy, progress-tracker):
**"takum32/64 = routing FAILURE on Artix-7 = horizon B, Tier-E ceiling = 71/83"**
— is **PARTIALLY REFUTED** by fresh evidence on #199 (08–13.07.2026).

The root of the "routing FAILURE" turned out to be a **functional 1-bit bug `S1_R`**, NOT
a physical limit of routing. The bug truncated the 3-bit regime field to 1 bit →
it corrupted the entire pipeline chain of the decoder. It masqueraded as a routing-limit
(and as "BRAM INIT red herrings"). After the fix + split-table approach:

- **takum32:** CI run [28935841570](https://github.com/gHashTag/trinity-fpga/actions/runs/28935841570)
  = `AX7203 Corona Decode TAKUM32`, `conclusion=success` `[proven — public API]`;
  SHA256 `eb402381…f170b0e48`; UART **65/65 bit-exact (fails=0)** (15 SSOT + 50 random).
- **takum64:** the same `S1_R` bug was found and fixed in `takum64_decode_pipelined.v`,
  the same split-table; iverilog 200/200; CI success (run 28959783877, UART 45/45).

### Split-table approach (what actually worked)

One 65536×48 table (did not fit / did not route) → **two 256×48 tables + a 48×48 multiplier**:
- `coarse[k] = round(2^(k/256) · 2^47)`, k=0..255
- `fine[j]   = round(2^(j/65536) · 2^47)`, j=0..255
- each table = one RAMB36E1 (eliminates multi-cell interleaving).

Artifacts already exist in the repo: `fpga/openxc7-synth/takum32_{coarse,fine,2frac}.mem`,
`corona_decode_takum32_ax7203.v`, `corona_decode_takum64_ax7203.v`,
host `conformance/takum{32,64}_decode_conformance_ax7203.py`, all vectors.

## What is ACTUALLY missing for Tier-E 4/4 (chain 3.5/4)

The Tier-E chain = (1) CI GREEN URL + (2) bitstream SHA256 + (3) UART `N/N fails=0` @160000 +
(4) IDCODE `0x13636093`. The takum32/64 evidence **has 1+2+3, but is MISSING the line (4) IDCODE** in the body.

**Diagnosed gap (verified):** the host scripts `takum{32,64}_decode_conformance_ax7203.py`
print only `HW RESULT: N/N bit-exact (fails=…)` — they do NOT print the IDCODE line.
But even the reference gf16 script does not automatically read the IDCODE — IDCODE `0x13636093` =
a **documented board constant** that the user copies from the flash step
(openXC7/JTAG) into the body of the proof. Hence the takum gap = **purely a documentation
gap (paste IDCODE), NOT a code gap and NOT a routing gap.** The RTL routes, CI is green, UART fails=0.

## What this changes for the ceiling

- The Tier-E ceiling **71/83 can no longer be called terminal on the grounds
  "takum does not route"** — this reason is refuted for takum32/64.
- As soon as the IDCODE line is added to the consolidated takum32 and takum64 proof →
  the chain 4/4 is closed → **decode-HW +2 → the union and the ceiling shift** (the exact
  tally to be re-checked against #199 after publication: takum8/16 were already in decode-HW, takum32
  and takum64 are added).
- This is `[REQUIRES USER ACTION]`: the user has the board and the IDCODE from
  each previous flash; one consolidated comment on #199 is needed.

## Honesty caveats (do NOT overestimate)

- takum64 silicon had a separate regression on the 2-stage pipeline (comment 4970163919:
  iverilog 9/9, but silicon 50.6%) — this is about **takum64 compute/pipeline**, NOT about
  decode. The decode chain (split-table) is the one that yielded 65/65 and 45/45.
- Other formats "outside 71" (non-takum, `[routing-pending]` gf24/gf32 decode) —
  their status is NOT changed by this analysis; they remain horizon-B candidates for
  THEIR OWN reasons (gf24/32 no-flatten CI = FAILURE, deeper routing-limit).
- Keep the number "ceiling 71" until the IDCODE line is published; do NOT move it retroactively.

## Task for the user (closes takum decode 4/4)

For takum32 and takum64 separately, on AX7203:
1. `openFPGALoader`/openXC7 flash the bitstream from the CI artifact of run 28935841570 (takum32)
   / 28959783877 (takum64) → the flash step prints IDCODE `0x13636093`.
2. `python3 conformance/takum32_decode_conformance_ax7203.py --port /dev/ttyUSB1 --baud 160000`
   → `HW RESULT: 65/65 bit-exact (fails=0)` (takum64 → 45/45).
3. One comment on #199 with the FULL 4/4 chain: CI URL + SHA256 + UART line +
   `IDCODE 0x13636093` line (from step 1). Then decode-HW takum32/64 = Tier-E.

## Link with gf24/gf32 (Track 2 of the same loop)

The opposite case to takum. For takum the "routing FAILURE" turned out to be a **functional
bug** (split-table cures the table). For **gf24/gf32 decode** the reason for horizon B is
**genuinely the depth of the combinational datapath** (barrel-shift + sticky-mask + CLZ +
rounding in one cloud), NOT a table → split-table is NOT applicable. The correct
technique is **pipelining**. A 2-stage
`fpga/openxc7-synth/gf_decode_param_pipe.v` is prepared (2-cycle latency, arithmetic is
bit-for-bit = original), proven by an iverilog testbench against an independent Fraction oracle:
**gf24 30000/30000, gf32 30000/30000 bit-exact** `[verified SW on iverilog]`.
Details — `conformance/witness/gf_pipe/README.md`. Whether the pipeline passes P&R on
Artix-7 — `[routing-pending]`, the verdict is ONLY openXC7 on the board
`[REQUIRES USER ACTION]`. This is a fix hypothesis, NOT Tier-E.

seed n/a (HW track).
