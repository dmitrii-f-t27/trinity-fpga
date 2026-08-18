# Where this work sits, and what nobody is checking

**Method note, stated first because it bounds everything below.** This is a
survey of repositories and their CI, read through the GitHub API on 2026-08-19.
It is **not** a literature review: the web search tooling was unavailable during
this iteration, and writing a prior-art section from memory is the exact failure
this project keeps documenting. Every claim below is a fact about a repository
that can be re-checked with one API call. Papers are unread and unmentioned.

---

## The landscape, by liveness

| project | stars | last push | CI workflows |
|---|---:|---|---|
| `YosysHQ/nextpnr` | 1726 | 2026-08-17 | active upstream |
| `f4pga/prjxray` | 906 | **2025-06-05** | Automerge, Pipeline |
| `chipsalliance/f4pga` | 447 | **2025-01-06** | — |
| `openXC7/nextpnr-xilinx` | 70 | 2026-08-18 | **one: `demos`** |

Two things follow, and neither is a value judgement.

**The database everybody depends on is dormant.** `f4pga/prjxray` has not been
pushed to in fourteen months. openXC7 maintains its own fork, which is why the
`bitread` use-after-free that made every 7-series bitstream unreadable had to be
fixed in `openXC7/prjxray#6` rather than upstream — and why the four missing
`I2IOCLK` rows blocking BUFR-from-a-pin need a fuzzer campaign run by whoever
wants them, rather than a request filed somewhere.

**The tool under active repair has one CI workflow.** `openXC7/nextpnr-xilinx`
is pushed to daily and gates on `demos` — it builds designs. A search of the
tree for `bit2fasm` returns nothing: **no comparison against a vendor bitstream
runs anywhere in that project's CI.**

---

## The gap, stated precisely

A design that builds is not a design that is configured correctly. Everything
found this month sat in exactly that gap:

| defect | builds? | correct? | how it was caught |
|---|---|---|---|
| SDP BRAM opposite-side widths (#150) | yes | no | Vivado golden, one-cell design |
| placed BUFR gets no configuration (#151) | yes | no | FASM diff, stock vs patched |
| `IFFDELMUXE3` suspected, then cleared (#114) | yes | yes | Vivado golden refuted the hypothesis |
| `I2IOCLK` row missing (#149) | yes | **no bitstream at all** | `fasm2frames` refused |
| `xc7a35t` cannot route a flop (#154) | **no** | — | part-to-part control |

Four of five produced a bitstream that a `demos`-style gate would call a pass.
One of those four could not be assembled into a bitstream at all, and the flow
only said so at `fasm2frames` — after place-and-route reported success.

**The instrument that found all of them is the same one:** decode the bitstream
and compare it against a vendor build of the identical design. It is not part of
any of these projects' CI, in either direction — neither openXC7 checking itself
against Vivado, nor a regression corpus of known-good FASM.

---

## What would close it, in ascending cost

1. **A golden corpus.** One-cell Vivado designs per primitive configuration —
   `IDDR` direct and delayed exist already, from #114 — decoded once and
   committed as FASM. Comparison then costs no licence and no vendor tool.
2. **A part-coverage gate.** #154 exists because nobody builds a flip-flop on
   `xc7a35t` in CI. A three-line design across the supported part list would
   have caught it the day it appeared. This is the cheapest item on the list and
   the one with the largest blast radius.
3. **A configuration diff in CI.** For designs where a golden exists, diff the
   emitted FASM against it and fail on a delta outside a stated allowlist.

Item 2 is worth arguing for upstream regardless of who does it. The other two
need a golden corpus first, and the goldens for `IDDR` were built by
@hansfbaier in an afternoon.

---

## What this repository can honestly claim

Not "we verify openXC7". What is true is narrower and checkable:

* five defects found in one month, four of them invisible to a build-only gate
* every one reduced to a minimal reproducer before being filed
* one hypothesis of my own **refuted** by the same method that confirmed the
  others (`IFFDELMUXE3`, #114) — which is the evidence that the method is not
  merely confirming what I already believed
* one claim of mine retracted after the file disagreed with it
  (`research/benchmark-timing-correction.md`)

The last two matter more than the count. A method that only ever confirms its
author is not a method.
