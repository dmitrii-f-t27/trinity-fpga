# TRI-NET — report, 2026-08-02

Written after the mesh ran on physical boards, and after an adversarial review
of that result. The review found seven fatal issues. Three are fixed; the other
four are structural, and this report leads with them rather than burying them.

---

## 1. The strongest sentence the evidence supports

> Two ALINX AX7203 boards, synthesised end to end on a fully open toolchain
> (yosys + nextpnr-xilinx), each run a 1336-logic-cell balanced-ternary
> dot-product cell with an in-fabric SipHash-2-4 tag engine. A single host
> process dispatched all 96 dot products of a three-layer forward pass to them
> over USB serial, independently recomputed every answer, and credited 96 of 96
> on three consecutive runs.

That establishes a dispatch → verify → settle path working end to end against
real silicon on an open flow. It establishes nothing about power, about compute
saved, about where the arithmetic actually ran, or about anything being a
network.

**"Ternary internet" is not defensible for two boards on one desk.** What is
defensible is "a verifiable ternary compute node, demonstrated on two boards".

---

## 2. Measured

| | |
|---|---|
| Ternary dot product + receipt, bit-exact on hardware | 512/512 (v1), 256/256 keyed (v2) |
| Keyed receipt rejects a wrong key | every job, measured both directions |
| Agent forward pass across two boards | 96/96 accepted, three consecutive runs |
| Throughput, one healthy board | **3786 jobs/s** (was 191 — 20× from batching, on top of 36× from transport work) |
| Logic cost | 1336 LC, **0 DSP48** |
| Software stack | 45 tests |
| CFGMCLK, measured per chip | 71.176 and 72.065 MHz — a **1.25% per-chip spread** |

Every number above came with a defect found by measuring rather than reasoning.
The four from the batching work alone: fixed-size blocks gave a whole layer to
one node; batching multiplies the cost of a lossy link; the read timeout was
2 s against a 1.2 ms round trip and accounted for 12 of 12.1 seconds; and the
frame parser lives in the FPGA and survives the host process, so runs degraded
3002 → 150 → 52 jobs/s until the port open began resynchronising the cell.

---

## 3. Competitive position — and it is genuinely unusual

Searched arXiv's API, GitHub's REST API and DuckDuckGo. **No multi-board FPGA
compute mesh with per-job verifiable receipts on an open toolchain exists**, in
2025-2026 or earlier. All three attributes are well populated separately; the
intersection is empty, and so are the pairwise intersections.

| | what exists | why it is not this |
|---|---|---|
| Multi-board FPGA compute | Brainwave (fleet, 2017-19), DFX (4× Alveo, MICRO'22), LoopLynx (dual, 2025), NeuroRing (Euro-Par'26), EMiX (8× U55c, 2026) | all vendor toolchains, none emits a per-job receipt |
| Ternary FPGA accelerators | TeLLMe, TENET, TerEffic; TernaryCore, ternfpga, STELE | single-board bar one, vendor tools, no receipts, no mesh |
| Verifiable compute | zkML, TEEs, opML, Gensyn Verde, EigenAI | a May 2026 survey lists **zero** FPGA-based schemes |
| FPGA DePIN | — | the category does not exist; every DePIN compute network is GPU |

**The sharpest competitive fact:** TerEffic — the only other multi-board ternary
FPGA work — reports numbers from *Vivado synthesis and power reports*, not from
a bench. Our numbers are measured on running boards. That is a different kind of
claim, and it is the one durable advantage found.

A GitHub code search for `siphash receipt language:verilog` returns three files,
all of them ours.

*Method caveat, stated because it matters: WebSearch was broken this session, so
searches ran through a browser against DuckDuckGo. The arXiv and GitHub index
zeros are strong evidence; the DDG zeros are softer.*

---

## 4. Seven fatal weak points

### Fixed today

**W01 — The receipt keys were committed to a public repository**, as
`0x00..0x0f`, `0x10..0x1f`, `0x20..0x2f`, in the Zig source, the RTL default and
the CI matrix. Guessable even had the repo been private. This destroyed the one
property keying the tag bought — *every "receipt verified" result before this fix
is unverified in the sense that mattered*. Keys now load from an uncommitted
file, `trinet keygen` prints fresh ones, the RTL default is visibly null, CI
artifacts are marked UNKEYED, and a run without keys says loudly that its
receipts are unverifiable.

**W03 — "96 on silicon" was a transport-type label, not a measurement.**
`isPhysical()` reports whether a serial port opened. Nothing in the job path
carries evidence of hardware origin. Now reads "dispatched to serial-attached
nodes", with the distinction printed inline.

**W05 — "Look damaged" was free, and my own corrupt-versus-lie fix had made it
the dominant strategy.** No credit either way, but no slash and no limit, so a
node could hold a dispatch slot forever delivering nothing. Damage still costs
no stake — an honest board on a bad cable must not be charged — but a node
delivering nothing usable is now marked unreliable and stops receiving work.

### Structural, not patched

**W02 — A symmetric MAC verified by the key holder is not a receipt.** The
coordinator holds every key, is the verifier, and is the ledger. No third party
can check anything. This is the deepest issue in the design: it makes the
receipt an internal consistency check, not evidence anyone else can rely on.
Fixing it means asymmetric signatures, which the FPGA cannot currently produce.

**W07 — The coordinator recomputes every job, so nothing is offloaded.** At a
100% audit rate the host does all the work the network does. This is inherent to
the current policy, and it means the demonstration is of *verification*, not of
*offload*. Offloading requires the audit rate to fall below 100%, which puts the
whole weight on slash economics — which brings us to:

**W06 — Stake is conjured, not deposited, and TRI has no external value**, so
the `p·s > r` soundness check is circular. There is no treasury, no conservation
invariant, and no path from credit to anything.

**W04 — Fleet identification is a trust step.** The coordinator asks a board its
id and uses the answer to choose which key verifies it. An attacker picks which
key they are checked against.

**W08 — No power figure of any kind.** Nothing has been on a bench supply.

---

## 5. Next wave

Ordered by what unblocks most. All nine are achievable with the two working
boards and no purchases.

| | | |
|---|---|---|
| WV-1 | Claim audit: every published sentence gets a file:line or a measurement, or it goes | |
| WV-2 | Re-establish the wrong-key result with keys that were never published | done |
| WV-3 | Replace fleet identification with a challenge-response | |
| WV-4 | Settlement rewrite: refusing must cost something, damage must still cost nothing | partly done |
| WV-5 | Bounded anti-replay window instead of an unbounded nonce map | |
| WV-6 | Measure the realised penalty rate instead of asserting the inequality | |
| WV-7 | Split `physical_asserted` from `physical_corroborated`; publish latency distributions | |
| WV-8 | Statistical base: 100 seeds, all runs reported — three runs of one seed will not survive review | |
| WV-9 | Restate throughput and scale honestly at the fleet operating point | |

---

## 6. Three options for the next loop

### A — A short paper with artifact evaluation (FCCM / ISFPGA 2027)

Framed narrowly: *a balanced-ternary MAC node with keyed work receipts on a
fully open Artix-7 toolchain — measurements and limits*. Three contributions
survive scrutiny: the openXC7 result (no peer-reviewed Artix-7 openXC7 design
was found, and the `DNA_PORT` characterisation appears unpublished); the
per-chip CFGMCLK spread as a fleet-reliability finding; and the keyed-tag law
separating hardware damage from dishonesty, derived from a real fleet failure
rather than a simulated adversary.

*Cost:* 6-8 weeks, and hard prerequisites — a power figure, a resource table in
Vivado vocabulary, and a statistical base.
*Risk:* two of three predictable referee attacks are severe. The receipt
authenticates a message, not an execution, and a 2026 measurement paper gives
referees a damning template for exactly that.
*Falsifier:* send the abstract to two people in the FPGA-accelerator community.
If both lead with "what is the power" and neither mentions the openXC7 or
damage-versus-dishonesty contributions, the framing is dead.

### B — Contribute the networking layer to the live ternary-FPGA cohort

There is an active 2026 cohort building single-board ternary accelerators with
**no networking layer at all**: TernaryCore (Arty A7-100T, hardware A/B posted
2026-07-25), Neumann-Labs/ternfpga, pingud98/stele-fpga. The mesh, receipt
engine and ledger are exactly the layer none of them has.

*Cost:* low in engineering, high in ego — weeks of outreach, and it costs sole
authorship.
*Risk:* they may not want a ledger. Single-board projects have no settlement
problem, and the layer we are proudest of may be the least valuable thing we
have to offer them. Their toolchains are Vivado/LiteX, so the openXC7
differentiator evaporates on contact.
*Falsifier:* open one issue on TernaryCore with a concrete integration sketch.
No substantive reply in 30 days is strong evidence the layer is not the
contribution we think it is.

### C — Qualification data package for a programme office

Stop treating this as a compute service; treat the ternary MAC cell as portable
soft IP with a characterisation package. Precedents are specific: the Swedish
National Space Agency funded Frontgrade Gaisler for a low-bit NN SoC; the US
government funded QuickLogic's rad-hard FPGA to an $89M ceiling. Open tooling is
a priced provenance argument in that market, not a hobbyist one.

*Cost:* by far the highest. Everything in Option A plus a real-process flow and
radiation data we have no way to produce. Discards the mesh, the ledger and the
TRI credit.
*Risk:* we have none of the four things every buyer needs — measured power,
device-bound identity, a trained model, a fab path. The market ceiling is
observably low. And LUT counts tuned to a 7-series carry chain are not portable
IP; the deliverable would be rebuilt, not repackaged.
*Falsifier:* one conversation with a named contact. If the first question is
"what is your TID/SEU data and your fab path", the track is not reachable from
here this year — and that answer is worth more than another quarter of building.

**Recommendation: B first, A second, C not this year.** B is cheap, and its
falsifier returns an answer in 30 days about whether the thing we built is
wanted by the people best positioned to want it. A depends on measurements we do
not have yet. C is an 18-month track that would be easy to mistake for a
3-month one.

---

## 7. Kill criteria

- A metered power figure lands and the ternary cell does not beat a CPU on
  joules per inference.
- No substantive reply from the ternary cohort in 30 days **and** no referee
  interest in the openXC7 framing.
- Nobody will name a workload expressible in ternary dot products.
- Any published claim is found to rest on evidence that cannot reproduce it.

---

Author: Dmitrii Vasilev ([@gHashTag](https://github.com/gHashTag))
Evidence: `specs/trinet/*.t27`, issue #199, `docs/TRI_NET_ARCHITECTURE.md`
