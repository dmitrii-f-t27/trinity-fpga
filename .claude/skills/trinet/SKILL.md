---
name: trinet
description: TRI-NET ternary internet — node cell, receipts, mesh, TRI settlement, IGLA CODER agent. Board truth, the honest status of every claim, and the next wave. Use when working on ternary compute nodes, compute receipts, the TRI credit ledger, or growing the network.
---

# TRI-NET

A network whose unit of work is a 32-wide ternary dot product, executed on FPGA
nodes, returned with a verifiable receipt, and settled as work credit.

Read `docs/TRI_NET_ARCHITECTURE.md` before changing anything. The two `.t27`
records are the source of truth for what is actually established:
`specs/trinet/ternary_hw_verification.t27` and `specs/trinet/settlement_law.t27`.

## Status — do not restate these upward without re-reading the specs

| Claim | Tier |
|---|---|
| trinet_mac32 dot product **and** receipt tag bit-exact on AX7203, 512/512 | `[measured on FPGA]` |
| the board answers a second independent host (Zig CLI, 64/64) | `[measured on FPGA]` |
| trinet_mac32 routed, 429 LC, 0 DSP48 | `[synthesised and routed]` |
| gfternary MUL bit-exact, 16/16 exhaustive | `[measured on FPGA]` — **but the datapath is FP32, not ternary** |
| mesh, ledger, adversary rejection | `VERIFIED_SW` (42 Zig tests) |
| three *physical* nodes exchanging work | not done — one board exists |
| a trained IGLA CODER model | does not exist on this workstation |
| a receipt proves work ran on an FPGA | **false**, and must not be claimed |

**Do not cite gfternary as a ternary-compute hardware result.** That cell
expands each 2-bit code into an FP32 constant, runs `gf_mul_param(8,23)`, and
re-quantises. It verifies the format's decode/compute/quantise law only.
`trinet_mac32` is the cell whose datapath is actually ternary.

**Three incompatible trit encodings live in this tree** — gfternary and
trinet_mac32 agree (`00`=0, `01`=+1, `10`=−1), TF3 swaps the signs
(`01`=−1, `10`=+1), and `ternary_mac_16` shifts them (`00`=−1, `01`=0, `10`=+1).
Wiring any two together without a converter produces sign errors that
arithmetic self-tests cannot catch, because each is internally consistent.

Keep **RTL written ≠ routed ≠ measured on the board** apart. A bitstream that
builds is not a measurement.

## Two results that bound what can be claimed

**Device DNA is a dead end on this toolchain.** `DNA_PORT` places, routes, and
answers over UART — 8/8 reads, correct framing, 57 bits reported — and `DOUT` is
**zero for all 57 bits** on an AX7203 through openXC7 (2026-08-01). All bits
zero points at the primitive not being configured by the bitstream rather than
at a wrong shift sequence; a vendor-toolchain build on the same board would
settle it and has not been run. **Do not re-run this probe expecting a different
answer** — and never let a zero DNA become a node id, or every board on this
flow claims `0x00000000`.

**Throughput is a UART property, by ~5600x.** Measured 202.6 jobs/s (6482
ternary MACs/s), p50 4.90 ms, against a transport ceiling of 410 jobs/s and a
*derived* compute ceiling of 2.3M jobs/s. Any performance claim about this node
is a claim about the serial line. **No power figure exists** — nothing here has
been on a bench supply, so any TOPS/W comparison would be fabricated.

## The receipt, and exactly how far it reaches

| tag | resists | does not resist |
|---|---|---|
| CRC-32 (`trinet_mac32`) | corruption, wrong job, replay, stale nonce | anyone at all — the function is keyless |
| SipHash-2-4 (`trinet_node_v2`) | third parties forging on an operator's behalf; with per-node keys, one operator forging for another | the operator forging their own — they hold the bitstream, so they hold the key |

Closing the remaining gap needs a key that never leaves the device: eFUSE or
BBRAM with an encrypted bitstream, or an external secure element. Until then
node identity is **asserted, not proven**, and must be described that way
wherever it is published.

## Files

```
fpga/vivado/trinet_mac32_ax7203.v              node cell: ternary MAC + CRC receipt
formal/trinet_mac32_tb.v                       UART-level testbench vs golden vectors
conformance/trinet_mac32_conformance_ax7203.py golden oracle + hardware host
.github/workflows/ax7203-trinet-mac32.yml      sim-gated synthesis
src/trinet/{protocol,serial,net,node,ledger,mesh,model,agent,main}.zig
specs/trinet/*.t27                             the record
```

## Commands

```bash
zig test src/trinet/agent.zig -lc                     # 42 tests, whole stack
zig build-exe src/trinet/main.zig -lc                 # CLI
./main selftest                                       # adversaries vs verifier
./main probe /dev/cu.usbserial-1110                   # verify a flashed board
./main demo                                           # mesh + agent + books

python3 conformance/trinet_mac32_conformance_ax7203.py --self-test
python3 conformance/trinet_mac32_conformance_ax7203.py --port /dev/cu.usbserial-1110 --n 512
```

Flash (13 minutes — pipeline other work against it):

```bash
sudo -n /opt/homebrew/bin/openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
  -c "init" -c "pld load 0 <file.bit>" -c "runtest 2000" -c "shutdown"
```

## Board and toolchain truths

- **Verify `sudo -n true` at the start of every flash session.** The
  `/etc/sudoers.d/openocd` rule has been lost to a reboot before.
- **A flash takes 778 s** for a 9.7 MB bitstream at the AL321's stable 100 kHz.
  Notes claiming ~78 s are wrong by an order of magnitude.
- **openocd's stdout is block-buffered** when redirected. An empty log file
  during a flash is not a hang.
- **Docker is often not running locally** — synthesis goes through CI.
- **CI workflows only register from `main`.** A push to a feature branch does
  not trigger them; cherry-pick onto a branch based on `origin/main` and push
  there.
- **The DSP guard must match the cell-count column**, `grep -E '^ *[0-9]+ +DSP48'`.
  Grepping the whole log for `DSP48` matches pass banners and fails a clean build.

## The bug class this project keeps producing

Every RTL defect found here has lived in the **frame path**, not the arithmetic.
Two more this session:

1. A conformance host emitted one byte too many, so operands shifted and the
   FPGA read `a = 0` for every job. It scored 7/16 — the exact cases whose
   answer is zero anyway. The golden oracle's self-test passed throughout,
   because it never exercised the wire encoding.
2. A testbench read hex fields with `$fscanf %h` and transmitted them low byte
   first, reversing every multi-byte field. The dot product could not see it —
   reversing both operands applies the same permutation to each.

**Therefore:** a conformance host is not verified by its self-test, and
arithmetic alone is not a sufficient witness for a wire format. Put a checksum
over the *inputs* in the response; it turns an invisible permutation into an
immediate localised failure.

## Design invariants — do not collapse these

- `node.execute` produces an **untrusted claim**; `protocol.verify` judges it
  against an independent recomputation; `ledger.settle` moves credit. Three
  steps, three functions. Merging them is how a compute network pays for work
  that never happened.
- A **tag can never adjudicate whose account a credit belongs in.** A node that
  computes honestly and signs as someone else passes the protocol verifier —
  refusing payment is the ledger's job.
- Full audit is affordable **because this work unit is small**. If the unit
  grows, lower the audit rate and raise the slash to keep `p·s > r`.
- No multipliers in the compute core. Ternary products need none, and DSP
  inference is what made every previous multiply cell unroutable under openXC7.

## The next wave

Ordered by what unblocks the most:

1. **Name a buyer.** `open_question WHO_BUYS_TERNARY_COMPUTE` in
   `settlement_law.t27`. `docs/TRI_NET_TECHNICAL_BRIEF.md` is written and ready;
   sending it is the operator's decision. Every other item is engineering; this
   one decides whether the engineering matters.
2. **Escape the UART.** Measured throughput is 0.02% of the derived compute
   ceiling. The USB-3 FIFO boundary issue #48 specifies is the unlock, and until
   it exists no performance number here means anything about the silicon.
3. **A second physical node.** Every distributed claim today is one board plus
   software. Two boards make the mesh real.
4. **Power on a bench supply.** No TOPS/W exists. Without it there is no
   defensible comparison against TernaryCore, TeLLMe or anyone else.
5. **TF3 balanced-ternary decode** (issue #234) — a different cell from any
   currently recorded, and blocked on picking one trit encoding for the tree.
6. **Device identity, if it matters enough.** A vendor-toolchain build of the
   DNA probe for comparison, or an external secure element. Do NOT simply
   re-run the openXC7 probe.

## Words that must not appear in any TRI-NET claim

"first", "best", "only", "beats". Also: never describe credited work as hardware
compute on the strength of a receipt alone.
