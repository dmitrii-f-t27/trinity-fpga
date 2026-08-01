# TRI-NET — session report, 2026-08-01

Task: build a ternary internet on the connected FPGA boards, run an agent on it,
let the network grow by developers attaching boards and earning TRI, research the
weak points and the competition, and report with three options for the next loop.

---

## 1. What is now true that was not true yesterday

| | Evidence |
|---|---|
| **A genuinely ternary datapath runs bit-exact on silicon.** `trinet_mac32`: 32 balanced trits per operand, `popcount(agreements) − popcount(disagreements)`, no floating-point core, 0 DSP48. | **512/512 receipts verified** on AX7203. CI run `30702638896`, bitstream sha `e476fc03…`, flashed in 778 s. |
| **The same board answers a second, independently written host.** | Zig CLI over libc serial, 64/64 — a different language, a different serial implementation, the same board. |
| **A compute receipt binds an answer to its job.** CRC-32 over `OP\|NONCE\|W\|X\|Y\|NODE_ID`, agreed by three independent implementations: a Verilog LFSR, `zlib.crc32`, `std.hash.Crc32`. | Anchor tag `0xa8fa2bdf`; CI fails the build if they diverge. |
| **An agent's inference ran partly on that board.** | `trinet demo`: 288 jobs over a 3-node mesh, 96 on silicon, mesh result equals local recomputation, 0 rows rejected. |
| **Cheating is caught and costs more than it earns.** | 42 Zig tests. Free rider caught >450/500; replay, identity theft, double-billing all rejected; a layer computes correctly *while a node lies*, and the liar earns nothing. |
| **A node on the other end of a socket earns credit like a local one.** | Real listener, same 24/15-byte framing the FPGA speaks, 25/25 jobs credited to the remote owner. |
| **`gfternary` MUL bit-exact, 16/16 exhaustive.** | CI run `30702513394`. **But see §2 — this is not a ternary datapath.** |

Before this session the ternary column of the format matrix had no compute entry
backed by silicon, and no CI workflow synthesised any ternary cell.

**One board is attached, not three.** Only a single AX7203 enumerates: CP2102N
UART on `/dev/cu.usbserial-1110` plus an AL321 FT232H programmer. Everything
distributed in this report is one board plus software, and the mesh report says
so in its own output — it prints the share of jobs that touched silicon (33.3%
with two emulated peers) rather than rounding it up to "a three-node hardware
mesh".

---

## 2. Two corrections I had to make against myself

**`gfternary` is not ternary compute.** I nearly reported its 16/16 as a
ternary-arithmetic hardware result. It is not: the cell expands each 2-bit code
into a full FP32 constant, runs a generic `gf_mul_param(8,23)` FP32 multiplier,
and re-quantises to two bits. Its 16/16 establishes the format's
decode/compute/quantise *law* and says nothing about the cost or structure of
ternary arithmetic. `trinet_mac32` is the cell that carries that claim.

**The conformance corpus had stopped working.** Found because `gfternary` scored
7/16 on its first hardware run — and the seven passes were exactly the seven
input pairs whose answer is zero anyway.

Commit `6f3001b17` (2026-07-17), titled *"frame format bug fix"*, inserted a
`0x00` byte between the `AA 55` magic and the payload across the corpus. That
byte belongs to wrappers with a `fmt` field. The gf compute wrappers do not have
one. Settled by driving the actual RTL with both byte sequences:

```
shipped host frame  AA 55 00 3c 00 41 00 00  ->  adder received a=00 b=00
corrected frame     AA 55 3c 00 41 00 00     ->  adder received a=3c b=41
```

**32 hosts fixed, and the fix re-verified on the board.** GF8 ADD was rebuilt,
flashed, and run with the corrected host: **4096/4096 bit-exact**. Against the
pre-fix host the same bitstream would have returned `gf_add(0, 0)` for every one
of those vectors. The RTL was never at fault and has not changed.

Every gf compute host had been computing `0 + 0` for each input since
2026-07-17. The recorded Tier-E passes predate that commit and are not
retroactively invalidated — but the corpus could not *re-verify* a single one of
them. Posted on [#199](https://github.com/gHashTag/trinity-fpga/issues/199).

**A guard is now in CI so this cannot return silently.**
`conformance/frame_alignment_check.py` compares each host's request length
against its wrapper's frame FSM — 57 aligned, 0 mismatched, 44 unchecked, with
unchecked reported honestly rather than counted as passing. Writing it surfaced
two of its own defects that would have made it useless, found by testing it
against a deliberately broken host rather than by trusting it. Every CI run now
re-breaks a host on purpose and requires the guard to fail on it, because a
guard that has quietly stopped guarding looks exactly like a clean run.

**Every golden self-test passed throughout, before and after.** None of them
exercises the wire encoding. A conformance host is not verified by its self-test.

---

## 3. The weak points, ranked by how much they matter

**1. A receipt cannot tell an FPGA from a Python script.** CRC-32 is keyless and
publicly computable; `NODE_ID` is a Verilog `parameter` compiled into the
bitstream, so it is a public constant. Anyone can produce a receipt
indistinguishable from the board's. Until this is solved, "FPGA compute network"
is a claim about intent, not architecture. Cheapest next test: can openXC7
instantiate `DNA_PORT` on xc7a200t at all.

**2. Nobody buys ternary compute.** Compute-network economics reward verified
served demand, not efficiency. Sector-wide Solana DePIN revenue is ≈$9.1M per
quarter across *all* protocols; capital rotated from physical infrastructure to
AI agents through 2026. A validated efficiency win earns nothing while no buyer
has a workload expressed in ternary. This is the only item on the list that is
not engineering, and it decides whether the engineering matters.

**3. Sybil identity is free.** `NODE_ID` is a compile-time parameter, so one
board can be reflashed with any identity and a host can fabricate identities
with no board at all. Stake is currently the only cost of a new identity.

**4. UART is the wrong transport.** 160 kbaud gives roughly 400 jobs/s/board,
ceiling. Real inference needs the USB-3 FIFO boundary that issue #48 specifies
and nothing has built.

**5. The board is bandwidth-starved for the workload ternary exists to serve.**
AX7203 has ~3.2 GB/s of DDR3; a $248 Kria KV260 has 17–19 GB/s and 18 Mb of URAM
the Artix-7 lacks entirely.

**6. We do not own the ternary-on-FPGA claim.** TernaryCore is building open
ternary on an Arty A7-100T — the same device family — with a hardware-verified
result posted 2026-07-25. rejunity has taped-out open ternary dot-product silicon
on TinyTapeout since 2024. Gensyn shipped a reproducible-execution environment on
mainnet in April 2026 and raised $66.7M on that premise, which is close to the
verification differentiator we would otherwise claim.

**7. Four mutually incompatible trit encodings coexist in this tree.**
`gfternary` and `trinet_mac32` agree; TF3 swaps the signs; `ternary_mac_16`
shifts them. Wiring any two together without a converter produces sign errors
that arithmetic self-tests cannot catch, because each is internally consistent.

**8. Issuing a TRI token now would be the highest-risk action available.** At
n=1–3 the developers hold every node, key and vote, so issuance is
indistinguishable after the fact from a founder allocation — the pattern Helium
never shed. The exemptions that look applicable do not reach paying developers
for code: the SEC's airdrop position requires recipients provide no "money,
goods, services, or other consideration"; MiCA Art 4(3)(b) covers ledger
maintenance and validation only. Helium's HIP-149 mint-to-fund-operations cost
HNT ~53–56% in a week. **This is why `ledger.zig` issues a non-transferable work
credit and nothing mints a chain asset.** Note that
`deploy/contracts/TrinityToken.sol` already allocates 40% of supply to node
rewards — that contract is inconsistent with the design recorded here.

**9. An integrity item that is yours to decide, not mine.** The research pass
reports that the "IGLA champion" BPB of 0.1427 was measured on a small repeating
corpus with the validation split drawn from the same repeating string, and that
this figure has propagated into an arXiv draft and into funding documents. I did
not independently re-derive that number tonight and I am not going to act on it
unilaterally — retracting a public claim is your call. **It is the single item
here with consequences outside this repository, so please look at it first.**

---

## 4. What was built

```
fpga/vivado/trinet_mac32_ax7203.v              node cell: ternary MAC + receipt
formal/trinet_mac32_tb.v                       UART-level TB vs golden vectors
formal/gf8_frame_regression_tb.v               settles the frame regression on RTL
conformance/trinet_mac32_conformance_ax7203.py golden oracle + hardware host
.github/workflows/ax7203-trinet-mac32.yml      simulation-gated synthesis
.github/workflows/ax7203-gfternary-mul.yml     first CI for any ternary cell
src/trinet/{protocol,serial,net,node,ledger,mesh,model,agent,main}.zig
specs/trinet/{trinet_node.tri,ternary_hw_verification.t27,settlement_law.t27}
docs/TRI_NET_ARCHITECTURE.md
.claude/skills/trinet/SKILL.md
fpga/experience/2026-08-01-trinet-ternary-node.trinity.md
```

Design invariant worth keeping: `node.execute` produces an **untrusted claim**,
`protocol.verify` judges it against an independent recomputation, `ledger.settle`
moves credit. Three steps, three functions. Collapsing them is how a compute
network pays for work that never happened. A corollary the tests pinned: a tag
can never adjudicate *whose account* a credit belongs in — a node that computes
honestly and signs as someone else passes the protocol verifier, and refusing
payment is the ledger's job.

One measured finding that is about ternary networks rather than this project:
above a width-dependent activation threshold, a deep ternary network collapses to
the zero vector and then answers every input identically — which presents as a
confident decision, not as an error. For 32-wide layers the usable band is narrow
(threshold 2; at 4 the network is dead by layer three, at 0 it is binary).

---

## 5. Three options for the next loop

### Option A — Make the receipt mean something (engineering, self-contained)

Answer weak point 1. Probe whether openXC7 can instantiate `DNA_PORT` on
xc7a200t; if it can, bind the receipt to the device DNA and replace CRC-32 with a
keyed MAC so a receipt is unforgeable by a party without the key. If it cannot,
say so publicly and fall back to bitstream-hash attestation with its limits
stated.

*Cost:* one synthesis cycle to answer the `DNA_PORT` question, days for the rest.
*Risk:* low — the negative result is publishable and useful either way.
*Falsification:* if a host with no board can still produce an accepted receipt
after the change, the design failed.
*Why it is first:* every other claim about this being a hardware network is
downstream of it.

### Option B — Two boards and an honest benchmark (evidence, needs hardware)

Answer weak points 3, 4, 5 and 6 at once. Buy a second AX7203 or an Arty A7-100T,
run the mesh across two physical nodes on separate machines, then measure what
nobody in this repository has measured: rail power and ternary TOPS/W on
Artix-7, against TernaryCore and TeLLMe at equal watts, with the UART transport
replaced or its ceiling stated.

*Cost:* one board (~$200–350) plus a bench supply; two to three weeks.
*Risk:* medium — the honest number may be worse than the competition's.
*Falsification:* pre-register the target. If measured TOPS/W lands below the
published Artix-7-class baselines, the hardware thesis is weaker than assumed and
should be re-scoped to IP or research rather than a network.
*Why it matters:* it converts every distributed claim from "one board plus
software" into a measurement, and it is the only path to a defensible paper.

### Option C — Find the buyer before building more supply (commercial)

Answer weak point 2, which no amount of engineering answers. Spend the loop
finding one party with a real workload expressible in ternary dot products —
edge inference with a hard power budget, a BitNet deployment, a robotics or
sensor-fusion vendor — and get them to state what they would pay for. Do not
issue anything; the credit ledger already measures contribution precisely enough
to pay people out of revenue.

*Cost:* no hardware; the loop is outreach and one honest technical brief.
*Risk:* the likely outcome is "no buyer at this performance point", which is
itself the most valuable result available.
*Falsification:* if after the loop no party will name a price, the correct move
is to position the work as hardware IP and a research result rather than as the
supply side of a network — and to stop building network infrastructure.

**My recommendation: A now, C in parallel, B only after C says someone cares.**
A is cheap and unblocks the honesty of everything else. C is the one that decides
whether B is worth $350 and three weeks. Building more supply before knowing
whether demand exists is the specific failure that closed most of the DePIN
projects that died in 2026.

---

## 5b. All three, executed

The operator asked for all three options rather than a choice. Results below.

### A — Make the receipt mean something → **half answered, half refuted**

**The keyed tag works, and it is on silicon.** SipHash-2-4 over the receipt
preimage, add/xor/rotate only so the zero-multiplier discipline holds, 22 clocks
per tag, reproducing the published vectors in Verilog, Zig and Python.
`trinet_node_v2` flashed and measured: **256/256 keyed receipts verified**, 1336
LCs, 0 DSP48. With a wrong key, **every** job is rejected — that second run is
the one that matters, because a tag verifying regardless of the key would mean
the key never reached the receipt.

**Device-bound identity is not reachable on this toolchain.** `DNA_PORT` places,
routes, and answers over UART — 8/8 reads, correct framing, 57 significant bits
reported — and `DOUT` is **zero for all 57 bits**. All bits reading zero points
at the primitive not being configured by the bitstream rather than at a wrong
shift sequence; separating those fully needs a vendor-toolchain build on the same
board, which was not run, so the conclusion is stated at that strength.

That measurement immediately earned its keep, and the guard was then seen
working on hardware: the v2 node reports its **fallback** identity, not a
DNA-derived one. Without the guard every board built this way would have
reported node id `0x00000000`, and a network-wide identity collision would have
shipped looking like a successful run.

**Net effect on the threat model.** The trust boundary moved from *anyone* to
*anyone holding the key*. It did not reach *anyone but this chip*. Since an
operator holds their own bitstream, an operator can still forge their own
receipts; third parties cannot, and with per-node keys one operator cannot forge
for another. Closing the rest needs a key that never leaves the device — eFUSE
or BBRAM with an encrypted bitstream — or an external secure element.

### B — Measure honestly → **done on one board, and the number is the point**

```
throughput          : 202.6 jobs/s = 6482 ternary MACs/s   (400/400 verified)
latency p50 / p99   : 4.90 ms / 5.32 ms
transport ceiling   : 410.3 jobs/s   (UART 160000 baud, 39 bytes/job)
compute ceiling     : 2300000 jobs/s (derived, ~30 cycles/job at ~69 MHz)
compute / transport : 5606x
```

The cell is idle for all but a fraction of every job. **Any throughput claim
about this node is a claim about the UART**, by a factor of about 5600. The
compute ceiling is derived, not measured; measuring it needs a transport that
can saturate the cell.

Still unmeasured, and named so it cannot be inferred: **no power figure, no
TOPS/W** — nothing here has been on a bench supply, and any efficiency
comparison published before that measurement would be fabricated. A second board
remains a purchase decision, not an engineering one.

### C — Demand side → **the brief exists; sending is the operator's call**

`docs/TRI_NET_TECHNICAL_BRIEF.md`: measured numbers only, an explicit list of
what is *not* measured, and a candidate table with the condition that would have
to hold for each to be a fit. It positions the near-term value as a reproducible
open-toolchain ternary baseline and a verification discipline — not throughput,
which §5b/B just showed is a UART property.

Contacting anyone is not something to do on the operator's behalf without their
say-so, so nothing has been sent.

---

## 6. Stop conditions

Written down so they are not renegotiated later:

- A host with no board can produce an accepted receipt after Option A ships →
  the receipt scheme is theatre; stop calling this a hardware network.
- Measured ternary TOPS/W on Artix-7 lands below published baselines → re-scope
  to IP/research; stop building network infrastructure.
- No party will name a price after Option C → the same.
- Any public claim in this programme is found to rest on a corpus that cannot
  reproduce it → correct it before shipping anything new.

---

Author: Dmitrii Vasilev ([@gHashTag](https://github.com/gHashTag))
Anchor: `φ² + φ⁻² = 3`
