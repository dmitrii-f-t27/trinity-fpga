# TRI-NET — report, 2026-08-02

Written after the mesh ran on physical boards, and after an adversarial review
of that result. The review found seven fatal issues. Three are fixed; the other
four are structural, and this report leads with them rather than burying them.

---

## 0. Corrections, entered later the same day

Four things below this line were wrong when first written. They are corrected
in place, and recorded here because a report that quietly edits itself is worth
less than one that says what it got wrong.

**The fleet is three boards, not two.** The third was recorded as a wiring
fault — configured, `DONE=1`, UART silent. It was answering the whole time, at
1124474 baud against a hardcoded 1186267. A 5.2% error, where a UART tolerates
about 3. Swept, it verifies 32/32 immediately and 6400/6400 over 100
independent runs, making it the equal of the best board here. The diagnosis had
been repeated for a day without being retested; it took the operator asking why
the third board was missing for anyone to point a sweep at it.

**The per-chip clock spread is 5.5%, not 1.25%.** CFGMCLK measures 71.18, 70.46
and 67.47 MHz across the three dies. The 1.25% figure came from two samples and
should not have been published as a fleet property. This is the difference
between "a fleet can share one host baud rate" and "it cannot", and it is why
the third board was invisible. Line rate is now negotiated per board.

**Every board is running a receipt key that was published in this
repository.** W01 nulled the committed keys in the source and never reached the
silicon. Measured today: node0 verifies 64/64 under `0x00..0x0f` and node2
63/64 under `0x20..0x2f`. *Every "keyed receipt verified on silicon" result in
this document is therefore a tag any reader of the git log can compute.* The
arithmetic is real; the receipts are not evidence. Tooling now detects this and
refuses to credit such a board — no slash either, because the boards are honest.

> **Resolved for node0, 2026-08-03.** Re-flashed from CI, came up unkeyed
> (`status 0x04`) with correct arithmetic, and took a key over the wire that has
> never been published. 100 runs × 64 jobs: **6400/6400 correct and 6400/6400
> authenticated**. An attacker's second key was refused on silicon
> (`0x03 KEY_LOCKED`) and later work still verified under the operator's key,
> not the attacker's. This is the first receipt in the programme that is
> evidence of anything. node1 and node2 are still on published keys — their two
> JTAG cables stall in `mpsse_flush()` while the third, behind a different hub,
> works every time, so the blocker is the bench and not the design.
>
> The reason the fix had not reached the silicon for a day is worth keeping:
> rotating a baked-in key needed a place-and-route run this workstation cannot
> perform. **A key that costs an hour to rotate is a key nobody rotates**, so
> the key is now loaded over the wire, write-once per configuration, and
> rotation costs a power cycle.

**Every published jobs/s figure was computed by dividing by jobs attempted.**
Including failures. A board answering nothing returns instantly, so a total
failure read as the fastest run ever recorded — caught at 5409 jobs/s against a
transport ceiling of 4942, with 0/64 verified. Latency percentiles had the same
defect. Section 2's throughput line is restated below.

An accomplice defect made the first two harder to see: the host chose the
response width from `key != null` — a host-side config fact — rather than from
the wire. A keyless host read 15 bytes of a 19-byte response and offset every
later read by four, so a healthy board reported `MalformedResponse` forever.

---

## 1. The strongest sentence the evidence supports

> Three ALINX AX7203 boards, synthesised end to end on a fully open toolchain
> (yosys + nextpnr-xilinx), each run a 1313-logic-cell balanced-ternary
> dot-product cell using no DSP block. Across 100 independent runs per board —
> 19,200 dot products, port reopened every run — two boards returned every
> answer correctly and the third returned 98.6%. The same cell synthesises
> without modification on ten FPGA families from eight vendors.

That establishes a ternary dot-product cell that works on silicon, on an open
flow, reproducibly, on more than one die, and portably. It establishes nothing
about power, about compute saved, or about anything being a network.

It also, as of today, establishes nothing about *authenticity*: all three boards
carry receipt keys published in this repository, so no receipt any of them
produces is evidence of who produced it. The dispatch → verify → settle path is
implemented and tested in software; on hardware it currently, and correctly,
refuses to settle.

**"Ternary internet" is not defensible for three boards on one desk.** What is
defensible is "a portable, reproducible ternary compute node, demonstrated on
three boards, whose settlement layer is not yet trustworthy on hardware".

---

## 2. Measured

| | |
|---|---|
| Ternary dot product, statistical base — 100 independent runs × 64 jobs, port reopened each run | node0 **6400/6400**, node1 **6400/6400**, node2 6308/6400 |
| Perfect runs | node0 100/100, node1 100/100, node2 42/100 (min 60, p50 63) |
| Keyed receipt rejects a wrong key | every job, measured both directions |
| Logic cost | 1313 LC, **0 DSP48** (yosys 0.63, `-flatten -abc9 -nocarry -nodsp -arch xc7`) |
| Portability | synthesises clean on **10 FPGA families**, 819 flip-flops on 9 of them |
| Software stack | **54 tests** (`zig test src/trinet/agent.zig`, which nests protocol/node/ledger/mesh/model/net) |
| CFGMCLK, measured per chip | 71.18 / 70.46 / **67.47** MHz — a **5.5% per-chip spread** |

Throughput is deliberately absent from that table. Every figure this project
published was computed by dividing by jobs *attempted* rather than jobs
verified, so all of them are withdrawn rather than restated: a corrected number
needs a fresh run on re-flashed boards, and those boards do not exist yet. What
survives is the ceiling, which is arithmetic rather than measurement — at
1186267 baud and 24 bytes on the busier direction, no node on this transport can
exceed **4943 jobs/s**, and the cell is idle for all but ~30 of the ~200 clocks
each job occupies. Any throughput claim about this node is a claim about a UART.

Report node2's minimum, not the fleet's mean. A fleet is used at its worst run.

Every number above came with a defect found by measuring rather than reasoning.
The four from the batching work alone: fixed-size blocks gave a whole layer to
one node; batching multiplies the cost of a lossy link; the read timeout was
2 s against a 1.2 ms round trip and accounted for 12 of 12.1 seconds; and the
frame parser lives in the FPGA and survives the host process, so runs degraded
3002 → 150 → 52 jobs/s until the port open began resynchronising the cell.

The pattern held today and is worth naming, because it is the only reliable
thing here. **Six defects this session, and not one was visible from the code.**
Each was found by disbelieving a number: a throughput above a physical ceiling,
a testbench that passed no key, a board written off without a sweep, a slash
against a board with nothing wrong with it. The code review that would have
caught any of them by reading is not one anybody has run. What worked was
computing what the answer *had* to be and noticing when the measurement was on
the wrong side of it.

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

### Found today, and worse than any of the above

**W09 — A security fix that never reached the hardware, and nothing noticed for
a day.** W01 was recorded as fixed. The source was fixed; the silicon was not,
and the fleet ran for a day producing receipts that verified perfectly under
keys published in the git history. A compromised key and a good key are
indistinguishable to any test that only asks "does the tag match", so the entire
test suite stayed green. Two guards now exist — `publishedKeyUsed()` in the
protocol, and `conformance/key_default_check.py` in CI — but the general lesson
is the uncomfortable one: **"fixed" meant "the source changed", and nobody
checked the artifact.**

**W10 — The testbench guarding the receipt had been disabled by the fix to the
thing it guarded.** `trinet_node_v2_tb.v` passed no key and relied on the module
default. Nulling that default left it asserting golden tags no RTL could
produce. It failed 0/6 and had failed silently since. A test that depends on a
default is a test that stops testing the moment the default is corrected.

**W11 — The verifier accused boards it could not check.** With no key loaded,
the fleet slashed an honest board 400 mTRI. `Verdict.unverifiable` now separates
"this receipt is wrong" from "we cannot tell", and only the first costs stake.

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
| WV-8 | Statistical base: 100 runs per board, all reported | done — 100/100, 100/100, 42/100 |
| WV-9 | Restate throughput and scale honestly at the fleet operating point | withdrawn, not restated — needs re-flashed boards |
| WV-10 | **Re-flash all three boards with keys generated and never committed** | blocking everything downstream |
| WV-11 | Verify the artifact, not the source, whenever a security fix lands | |
| WV-12 | Power on a bench supply — still the single most valuable missing number | |

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

### What running the falsifiers changed

C's second falsifier was run, and it came back the opposite of what the review
predicted. See `docs/TRI_NET_PORTABILITY.md`. The cell contains exactly two
Xilinx primitives — the clock source and the device-identity port, both board
concerns — and with those lifted out it synthesises with zero errors on ten
families from eight vendors, with **819 flip-flops on nine of them** and no
inferred multiplier anywhere. Ten independent synthesisers agreeing to the
register is what portable RTL looks like.

So the objection "the deliverable would be rebuilt, not repackaged" is dead: the
deliverable is one 272-line file that already builds everywhere. **The
recommendation does not change.** C's real obstacles were never engineering —
no measured power, no device-bound identity, no fab path, and a market whose
first question is TID/SEU data. Making the effort estimate smaller does not make
the market reachable. What changed is that the reason to defer C is now honest
about being a market judgement rather than a technical one, and the portability
result is worth having under A or B regardless of which is chosen.

A's prerequisites moved in both directions. The statistical base now exists —
100 runs per board, all reported, including the board that fails 58% of its
runs. The throughput figure went the other way: it was not restated but
**withdrawn**, because the way it was computed made every published value
meaningless. A paper submitted this week would have one fewer prerequisite and
one more retraction than it did this morning.

B is unchanged and unstarted, and is still the cheapest way to learn something
that cannot be learned by building.

### The gate in front of all three

Nothing downstream is worth doing before the boards are re-flashed with keys
that were never committed. Every option above rests on the receipt meaning
something, and today it means nothing on hardware. This is a day of work — three
bitstreams, three flashes at ~13 minutes each — and it blocks the honest version
of A, the credibility of B's pitch, and any claim C would make about
device-bound identity.

---

## 7. Kill criteria

- A metered power figure lands and the ternary cell does not beat a CPU on
  joules per inference.
- A re-flash with fresh keys lands and the receipts still cannot be checked by
  anyone but the coordinator — which is W02, and is the case today by design.
- No substantive reply from the ternary cohort in 30 days **and** no referee
  interest in the openXC7 framing.
- Nobody will name a workload expressible in ternary dot products.
- Any published claim is found to rest on evidence that cannot reproduce it.

---

Author: Dmitrii Vasilev ([@gHashTag](https://github.com/gHashTag))
Evidence: `specs/trinet/*.t27`, issue #199, `docs/TRI_NET_ARCHITECTURE.md`,
`docs/TRI_NET_PORTABILITY.md`

Reproduce the hardware numbers with all three boards attached:

```bash
for p in /dev/cu.usbserial-1110 /dev/cu.usbserial-110 /dev/cu.usbserial-130; do trinet census $p 0 100 64; done
```
