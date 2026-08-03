# TRI-NET — handoff

Written 2026-08-03 so the next person can continue without the conversation
that produced this. It is meant to be read top to bottom once, then used as a
reference. Where it states a number, that number was measured; where it states
a limit, the limit was hit.

Branch `trinet-fleet-truth`, PR
[#355](https://github.com/gHashTag/trinity-fpga/pull/355), 19 commits ahead of
`main` at time of writing.

---

## 1. What the fleet is, right now

Three ALINX AX7203 boards (Artix-7 `xc7a200tfbg484-2`), all running the same
cell from CI artifacts, all keyed with per-node secrets that have never been
published.

| node | id | port (today) | line rate | JTAG | health |
|---|---|---|---|---|---|
| node0 | `0x5452494E` | `/dev/cu.usbserial-110` | 1 186 267 | `0-1.2` | 6400/6400 |
| node1 | `0x5452494F` | `/dev/cu.usbserial-1110` | 1 124 474 | `1-1.2` | 6400/6400 |
| node2 | `0x54524950` | `/dev/cu.usbserial-1130` | 1 174 399–1 186 267 | `1-1.4` | 6245/6400 |

**Every column except `id` is unstable.** Port names move when hubs change —
`-1110` was node0 one hour and node1 the next. JTAG locations move with them.
Line rates differ per board because CFGMCLK is an untrimmed RC oscillator and
these three dies run at **71.18 / 70.46 / 67.47 MHz — a 5.5% spread** against a
UART tolerance near 3%.

Never identify a board by its device name or by argument order. Ask it:

```bash
python3 conformance/trinet_discover.py
```

### Keys

`trinet-keys.txt` in the repo root, mode 600, gitignored — **verify that before
every commit**. It maps node name → 16-byte key. It is not in git and there is
no other copy: lose it and the boards must be power-cycled and re-keyed (which
now costs seconds, see §3).

---

## 2. The measurement of record

100 independent runs × 64 jobs per board, port reopened every run — that
matters, because the FPGA's frame parser holds state across host processes.

| | dot products | receipts authenticated | perfect runs |
|---|---|---|---|
| node0 | 6400/6400 | **6400/6400** | 100/100 |
| node1 | 6400/6400 | **6400/6400** | 100/100 |
| node2 | 6245/6400 (97.6%) | 6235/6400 | 25/100, min 59 |

Agent forward pass across all three: **96 of 96 accepted, 0 rejected, 0
slashed, 96 mTRI credited, all three nodes active.**

Reproduce:

```bash
for p in /dev/cu.usbserial-110 /dev/cu.usbserial-1110 /dev/cu.usbserial-1130; do trinet census $p 0 100 64; done
```

**Report node2's minimum, not the fleet's mean.** Its losses are the link, not
the key or the clock: swept to its own centre rate it scored slightly *worse*
(98.08% vs 98.56%), which cleanly falsifies the baud hypothesis.

### Numbers that are withdrawn, not restated

**Every jobs/s figure this project ever published is void.** They divided by
jobs *attempted*, not verified, so a board answering nothing read as the fastest
run ever recorded — 5409 jobs/s against a transport ceiling of 4942, with 0/64
verified. The bench now counts verified work only and prints `IMPOSSIBLE` above
the ceiling. A corrected throughput number needs a fresh run and nobody has
taken one.

What survives is the ceiling, which is arithmetic: at 1 186 267 baud and 24
bytes on the busier direction, **no node on this transport can exceed ~4943
jobs/s**, and the cell is idle for all but ~30 of the ~200 clocks per job. Any
throughput claim about this node is a claim about a UART.

**Still no power figure of any kind.** Nothing has been on a bench supply. This
is the single most valuable missing measurement and it blocks the paper.

---

## 3. How the key works now (changed 2026-08-03)

`RECEIPT_KEY` used to be a synthesis parameter. It was committed to a public
repository, the fix was applied to the source, and **the fix never reached the
silicon** — the fleet ran for a day signing with keys any reader of the git log
could compute, while every test stayed green, because a compromised key and a
good key are indistinguishable to anything that only asks "does the tag match".

The reason it never reached the silicon is the part to keep: rotating a baked-in
key needs a place-and-route run **this workstation cannot do** (see §5), plus 13
minutes of flashing, per board. *A key that costs an hour to rotate is a key
nobody rotates.*

So the node takes its key over the wire:

- `op 0x02`, 16 key bytes in the W and X operand fields. The request stays 24
  bytes, so the frame parser and `conformance/frame_alignment_check.py` are
  untouched.
- **Write-once per configuration.** A second `setkey` returns `0x03 KEY_LOCKED`
  and changes nothing. Proven on silicon against an attacker's key, not only in
  simulation.
- The acknowledgement is **signed with the key just installed**, so acceptance
  is distinguishable from an echo. `Node.setKey` checks the tag, not the status.
- An unkeyed board answers `0x04 NO_KEY` with a **real** dot product. Anything
  measuring arithmetic must call `protocol.statusMeansComputed()`.
- A non-null `RECEIPT_KEY` still bakes a key in and locks it at reset, for
  anyone with a build machine who prefers the key never touch a wire. CI must
  never pass one.

Cost: 1292 → 1484 LC (+15%), still 0 DSP48.

**The trade, stated plainly:** whoever reaches this UART in the window after
configuration can claim the node. They can also just re-flash it, so this
concedes little that physical access did not already concede, and it buys a
rotation cheap enough to actually happen.

---

## 4. Bringing a board up, in order

```bash
# 1. Who is on the bus, and at what rate
python3 conformance/trinet_discover.py

# 2. Find the JTAG locations — from ioreg, never guessed
ioreg -p IOUSB -w0 | grep -E "Hub|Digilent|CP2102N"
#   Digilent USB Device@01120000  ->  openocd location 1-1.2
#   (first byte = bus, each remaining non-zero nibble = a port down the chain)
#   A CP2102N and a Digilent under the SAME hub are the same board.

# 3. Flash — 778 s per board, and they run in PARALLEL on separate programmers
sudo -n /opt/homebrew/bin/openocd \
  -f fpga/openxc7-synth/ax7203_al321_multi.cfg \
  -c "adapter usb location 1-1.2" -c "init" \
  -c "pld load 0 build/fleet/trinet-fleet-node1/trinet_node1.bit" \
  -c "runtest 2000" -c "shutdown"
# NOTE: the copies currently on disk are in ...-node1-UNKEYED/ — they predate
# the artifact rename. That suffix was dropped because these bitstreams are
# complete and deployable now; a build after 06e781644 has no suffix.

# 4. Confirm the NEW bitstream is running: it must answer status 0x04 NO_KEY
# 5. Key it
trinet keygen > trinet-keys.txt      # only when starting fresh; mode 600
trinet setkey <port0> <port1> <port2>

# 6. Now it can settle
trinet fleet <port0> <port1> <port2>
```

Bitstreams come from CI:

```bash
gh workflow run ax7203-trinet-fleet.yml --ref <branch>
gh run download <run-id> --dir build/fleet
```

**Verify the artifacts before flashing:** the three `.bit` files must have
*different* sha256s. Identical ones mean the `node_id` chparam did not take, and
all three boards would claim the same identity — discoverable only after three
13-minute flashes.

---

## 5. Environment limits, measured not assumed

- **No local place-and-route.** 8 GB host RAM. Docker's default 4 GB OOM-kills
  `bbaexport` for `xc7a200tfbg484-2`; raising it to 6 GB stops the Docker VM
  starting at all. Any plan step assuming a local bitstream build is dead on
  arrival. Use CI.
- **`sudo` is narrow.** `/etc/sudoers.d/openocd` grants NOPASSWD for
  `/opt/homebrew/bin/openocd` **and nothing else**. `sudo -n pkill` therefore
  fails with "a password is required", and with `-n` it fails *silently*. It
  does not survive a reboot — check `sudo -n /opt/homebrew/bin/openocd --version`
  at the start of every flash session.
- **openocd needs root** on macOS: `AppleUSBFTDI` claims the FT2232H, so a
  non-root openocd reports "no device found".
- **All AL321 cables share USB serial `210512180081`**, so `adapter usb
  location` is mandatory with more than one attached.
- A flash takes **778 s**, not the ~78 s some old notes claim. openocd's stdout
  is block-buffered when redirected, so an empty log during a flash is not a
  hang.

---

## 6. Traps that cost real time here

**Bound a privileged probe correctly.** Backgrounding `sudo`, capturing `$!` and
`kill -9`-ing it does **not** work: `$!` is the sudo wrapper, openocd runs as
root beneath it, and a user kill cannot touch a root child. The wrapper dies,
the timeout looks like it worked, and the adapter stays held. Two leaked
processes wedged two cables for nearly three hours. Put the timeout inside:

```bash
sudo -n timeout -s KILL 25 /opt/homebrew/bin/openocd -f <cfg> -c "init" -c "shutdown"
```

**`mpsse_flush()` stall ≠ dead cable.** Order of suspicion: leaked openocd
first (`ps -eo pid,stat,etime,comm | grep openocd`), then replug the cable, then
board power. A bus-position theory was recorded here confidently and was wrong —
three consistent observations of a correlation are not a cause.

**A board that does not answer has not been tested until it has been swept.**
node1 was written off as a wiring fault for a day. It was answering the whole
time at 1 124 474 baud, 5.2% off the hardcoded rate.

**Verify the artifact, not the source.** Three separate defects this session
came from a fix that changed source and never reached the thing that runs.

---

## 7. The recurring defect, named

Six defects this session, and **not one was visible from reading the code**.
Each was found by disbelieving a number: a throughput above a physical ceiling;
a testbench that passed no key; a board written off without a sweep; a slash
against a board with nothing wrong with it.

Three of them had the *same shape*: **a rule written in one place, enforced by
enumerating cases somewhere else.**

- `Verdict.unverifiable` was added so a keyless verifier could not accuse.
  `ledger.settle()` never asked — it named `.corrupt` as the one verdict that
  costs nothing and slashed everything else. Two honest boards lost 600 mTRI
  each for keys *we* could not check.
- The mesh's outcome accounting had a catch-all that printed "39 rejected as
  dishonest" beside "slashed: 0 mTRI". A summary that accuses and then charges
  nothing is either a lie or a bug and a reader cannot tell which. It was two.
- `setkey` counted a board as keyed only if 32/32 later jobs came back clean, so
  a successfully keyed board was reported as not keyed, hidden behind its own
  lossy cable.

The structural fix, applied: **ask, don't enumerate.** `settle()` now calls
`verdict.indictsTheNode()`, and the mesh's switch is exhaustive with no `else`,
so adding an outcome is a compile error until someone decides what it means.

Apply the same test to new code: *if someone adds a case tomorrow, does this
default to safe, or does it default to accusing an honest operator?*

---

## 8. What is still open

### Structural, unfixed, and stated in the report rather than buried

- **W02 — a symmetric MAC verified by the key holder is not a receipt.** The
  coordinator holds every key, is the verifier, and is the ledger. No third
  party can check anything. This is the deepest issue in the design; fixing it
  needs asymmetric signatures the FPGA cannot currently produce.
- **W07 — the coordinator recomputes every job, so nothing is offloaded.** At a
  100% audit rate the host does all the work the network does. The demonstration
  is of *verification*, not of *offload*.
- **W06 — stake is conjured, not deposited**, and TRI has no external value, so
  the `p·s > r` soundness check is circular.
- **W04 — fleet identification is a trust step.** The coordinator asks a board
  its id and uses the answer to choose which key verifies it.
- **W08 — no power figure.** Blocked on a bench supply.

### Next actions, in the order they unblock most

1. **Option B — the TernaryCore issue.** Draft written and *held* at
   `docs/outreach/ternarycore-issue-draft.md`. It was held because its strongest
   line ("per-job verifiable receipts, demonstrated on silicon") was false. **It
   is now true.** Needs the operator's go-ahead — it is outward-facing to a third
   party. Falsifier: no substantive reply in 30 days.
2. **A power measurement.** Everything about efficiency is unclaimable without
   it, and referees will lead with it.
3. **Restate throughput** with the corrected counter, on the re-keyed fleet.
4. **node2's link.** 97.6% and 25/100 perfect runs. Not the baud, not the key —
   try a different cable and a different hub port before believing the board.
5. **Option A — the paper.** The statistical base and the portability result now
   exist; power does not.

### Portability (option C), answered

The cell contains exactly two Xilinx primitives — `STARTUPE2` for the clock and
`DNA_PORT` for identity, both board concerns. With those in a wrapper, the core
in `fpga/portable/trinet_node_core.v` synthesises **with zero errors on ten FPGA
families from eight vendors**, with **819 flip-flops on nine of them** and no
inferred multiplier anywhere. See `docs/TRI_NET_PORTABILITY.md`.

This does not establish portability of *product*: synthesis is not P&R, no
non-Xilinx mapping has met timing, and only xc7 has run on silicon. And it does
not make anyone want the IP — C's real obstacles were never engineering. The
recommendation to defer C stands.

`DNA_PORT` is now compiled out (`USE_DNA=0`): it places, routes, and returns
zero for all 57 bits on this flow, so it was dead weight in every bitstream, and
removing it makes the node id in simulation equal the one hardware reports.

---

## 9. Where things live

```
fpga/portable/trinet_node_core.v          the node, no vendor primitives
fpga/vivado/trinet_node_v2_ax7203.v       AX7203 wrapper — instantiates the core,
                                          never a copy, or the claim rots
fpga/openxc7-synth/trinet_siphash24.v     receipt tag engine
formal/trinet_setkey_tb.v                 the key-over-the-wire law, 11/11
formal/trinet_node_v2_tb.v                keyed receipts, 6/6
tools/gen_setkey_golden.py                goldens from Python, never from RTL
conformance/trinet_discover.py            who is on the bus, at what rate
conformance/trinet_baud_sweep.py          a board's real rate
conformance/key_default_check.py          null RTL defaults, explicit test keys
conformance/portability_check.py          the ten-family invariant
src/trinet/{protocol,serial,net,node,ledger,mesh,model,agent,main}.zig
specs/trinet/ternary_hw_verification.t27  THE RECORD — claims, limits, retractions
docs/TRI_NET_REPORT_2026-08-02.md         the report, with its corrections at the top
docs/TRI_NET_PORTABILITY.md               the ten-family measurement
docs/outreach/ternarycore-issue-draft.md  option B, written and held
.claude/skills/trinet/SKILL.md            operational truth; read before touching hardware
```

**`specs/trinet/ternary_hw_verification.t27` is the source of truth for claims**,
including a `retracted` entry where this session got a cause wrong. Add to it
rather than to prose when something is measured.

Tests: `zig test src/trinet/agent.zig -lc` runs **56** tests and nests every
other module's. Do not sum the per-file suites — that was done here and reported
as 180, then 198, both wrong.

---

Author: Dmitrii Vasilev ([@gHashTag](https://github.com/gHashTag))
