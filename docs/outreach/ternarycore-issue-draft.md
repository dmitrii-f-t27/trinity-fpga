# Draft: issue for TernaryCore (option B)

**Status: NOT SENT.** Held deliberately — see the note at the bottom, which is
the reason and is not a formality.

Target: the TernaryCore repository (Arty A7-100T, hardware A/B posted
2026-07-25). Secondary targets if this lands: Neumann-Labs/ternfpga,
pingud98/stele-fpga.

The falsifier attached to option B: *no substantive reply in 30 days is strong
evidence the layer is not the contribution we think it is.*

---

## Title

Offering a verified-dispatch layer: has multi-board come up for TernaryCore?

## Body

Hello — I've been building a balanced-ternary MAC node on an Artix-7 through the
fully open toolchain (yosys + nextpnr-xilinx, no Vivado), and I've ended up with
a networking and verification layer that seems to be the piece single-board
ternary projects don't have. Rather than assume it's useful, I'd rather ask.

**What I have that might be relevant to you.** A host dispatches individual dot
products to boards over a serial link and independently recomputes each answer
before accepting it, so a wrong or damaged result is caught per job rather than
per run. Each board signs its answer in fabric with a keyed tag, which is what
lets the host tell a lying node from a bad cable — that distinction turned out to
matter more than I expected, because my first version penalised an honest board
for a marginal USB link. The whole thing runs across three boards at once, with
each board's line rate negotiated rather than assumed.

**The concrete integration.** If TernaryCore exposes a request/response over
UART or PCIe with a stable frame, the layer above it is roughly:

- a 24-byte request `AA 55 OP NONCE[4] W[8] X[8] TRIG` and a 19-byte response
  `A5 Y STATUS NONCE[4] NODE_ID[4] TAG[8]` — or whatever framing you already
  have; the layer only needs a nonce it can match and a result it can recheck
- a SipHash-2-4 tag engine, ~1300 LC, add/xor/rotate only, no DSP and no
  multiplier; 22 clocks per receipt
- a host-side dispatcher and verifier that batches per node with AIMD, because
  batching is an optimisation on a healthy link and a liability on a lossy one

All of it is Apache/MIT-compatible and I would rather it lived in your tree than
mine if it's useful to you.

**Three things I'd genuinely like to know, and where "no" is a useful answer:**

1. Has multi-board come up for TernaryCore at all, or is single-board the point?
2. If it has — do you verify results per job today, or trust the accelerator?
3. Would an open-toolchain path matter to you, or is Vivado/LiteX fine?

If the answer to all three is "not really", that's worth knowing and I'll stop
pitching it. I'm not looking for anything from you except whether this is real.

**What I can back with measurements**, so you can weigh it: the dot-product cell
is 1480 LC with zero DSP on xc7, and it synthesises unmodified on ten FPGA
families from eight vendors, with 819 flip-flops on nine of them. On hardware,
across 100 independent runs of 64 jobs per board: two boards at 6400/6400 and a
third at 6308/6400. What I *cannot* back yet is any power figure, and the receipt
authentication is currently unverifiable on my own boards for a reason described
in my repo — the honest version is that the arithmetic is proven and the
settlement layer is not.

---

## Why this is not sent yet

The pitch's strongest line would have been "per-job verifiable receipts,
demonstrated on silicon". That line is not true today.

All three of my boards are flashed with receipt keys that were published in my
own git history. The software fix that nulled those keys never reached the
bitstreams, and the fleet ran for a day producing receipts that verify perfectly
and prove nothing. Anyone who read the repository could compute the same tags.

So the layer I would be offering has a working implementation, 180 passing
tests, and a hardware demonstration whose central security property is currently
void. Sending this before re-flashing means either overstating it — which is the
one thing that would make the 30-day falsifier meaningless, because a polite
non-reply would then be the correct response — or explaining the flaw in the
opening message, which is a strange way to introduce yourself.

**Send after:** three bitstreams rebuilt with keys from `trinet keygen`, flashed,
and `trinet fleet` settling work end to end on all three boards. That is about a
day of work. The draft above already carries the honest caveat in its last
paragraph and should keep it either way — but it should be a footnote about a
solved problem, not a description of the current state.
