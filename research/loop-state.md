# Loop state — autonomous improvement cycle

Journal for the `/loop` cron job (`*/15 * * * *`). **Read this before doing anything.**
Its purpose is that a later iteration does not redo, undo, or contradict an
earlier one. Append; do not rewrite history.

## Invariants — do not violate

1. **Never claim without measuring.** Every assertion here carries either a run
   URL, a commit SHA, or a file:line. If you cannot produce one, write
   "unverified" next to the claim rather than dropping it.
2. **Never fix by guessing at someone else's API.** Read the implementation.
   Three defects this session came from code written against an API that had
   moved; a fourth nearly came from me substituting a plausible signature.
3. **Do not push to `main` without the gate passing**, unless the commit is
   explicitly a diagnosis (say so in the message).
4. **Do not touch the user's main checkout** at `/Users/playom/trinity-fpga` —
   it has uncommitted work on branch `trinet-fleet-truth`. Work in a worktree.
5. **A red gate is information, not an emergency.** Report where it stopped;
   do not disable it, loosen it, or edit the test so it passes.
6. **Board work is the user's.** Anything needing the AX7203 waits for them.

## Current state of the long threads

| Thread | State | Evidence |
|---|---|---|
| `tri` build | Restored, compiling further each round | gate `tri builds` |
| BUFR configuration | **Fixed upstream, merged** | nextpnr-xilinx#151 |
| BUFR from a pin | Blocked on prjxray `047b` (I2IOCLK rows) | issue #149 comment |
| IDDR / #114 | Site config eliminated; 4 `IFF.ZSRVAL_Q` bits left | issue #114 comment |
| Benchmark write-up | Two corrections owed, not yet written | — |
| `zig-golden-float` | **Unpushed commits — clone --recursive fails for everyone** | README |

## Iteration log

### 001 — 2026-08-18

**Did.** Resolved the zig-hdc API drift that blocked the `tri` build, by reading
the implementation rather than guessing at it:

* `zig-hdc` turned out to be a thin re-export of `zig-golden-float`, which is
  checked out locally — so the real signatures were readable.
* `bundle2(a, b)` takes two arguments; our callers passed three. The third was
  an allocator the current implementation does not want.
* `getTritChecked` was renamed `getTrit`, and the new one is still
  bounds-checked (`if (pos >= self.trit_len) return 0`), so the substitution
  preserves semantics. Verified before applying, not after.

**Found, worth carrying forward.** `zig-hdc`'s own header records the reason it
became a re-export: two maintained copies of `src/vsa/*` had diverged, so
repairing sixteen defects in one left all sixteen standing in the other. That is
the same failure mode as everything else found today — a reference left pointing
at a thing that moved — and it argues for the general rule in the skills file.

**Left deliberately.** `src/query_cli.zig` and `src/sota_report_demo.zig` still
pass an allocator to `bundle2`. They are not in `tri`'s module graph, so nothing
has compiled them against the current signature. Fixing them now would be a
guess about which `bundle2` they resolve to; the compiler will say when it
reaches them.

**Next.** Whatever the gate reports. Then: the two benchmark corrections, and a
minimal reproducer for the `Invalid global constant node` router failure.

### 002 — 2026-08-18, same evening

**Method change that paid for itself.** Fixing "no module named X" one CI round
at a time was costing a build per defect and finding them in the compiler's
order rather than mine. Enumerated instead: 34 named imports under `src/tri`,
21 wired, 13 missing. All 13 in one commit. Prefer the inventory to the
iteration whenever the defect class is enumerable.

**Defects closed this round.** zig-hdc API drift (`bundle2` arity,
`getTritChecked` → `getTrit`), 13 unwired modules, `golden_chain` bound to the
wrong file of that name, an orphaned parameter, a `{m}` format specifier, 14
C-style `{:.3f}` specifiers, `for` over an `ArrayList` instead of `.items`,
`catch unreachable` on a void, `'●'` assigned into a `u8`, and
`totalVelocity` called with an allocator it no longer takes.

**Two of them were mine**, both caught by the gate rather than by me:
dropping `bundle2`'s allocator orphaned `store()`'s parameter, and a
`grep 'pub const GoldenChain'` matched `GoldenChainAgent` by prefix, so I wired
a module to the wrong file on a fuzzy name match. Both now have a habit
attached: after removing an argument, check the enclosing function still uses
its parameter; and a prefix match is not an identity match.

**The recurring shape, now with six instances.** Every structural defect found
today is the same one: code moved out, a reference stayed behind.
`local_farm.zig` (farm → trinity-training), `src/vsa.zig` (VSA → zig-hdc),
`quantum_gravity_full.zig` (physics → zig-physics), the zig-hdc API drift after
its own dedup, `build.zig` itself, and the submodule gitlink pointing at an
unpushed commit. None was caught at extraction time, because nothing ran the
build.

**Instrument improvement.** Added `-freference-trace=12` to the gate after a
comptime format error reported std's line and hid the call site behind "8
reference(s) hidden". It named the real line on the first run afterwards.

**Judgement worth keeping.** `'●'` in a `u8` would also have compiled if I had
swapped it for ASCII — and would have silently downgraded the plot. The print
loop already emitted the glyph as a literal and only used the buffer as a
marker, so markers were the correct fix. The cheaper repair is not always the
smaller change.

**Next.** Whatever the gate says. Then the two benchmark corrections, and a
reduced test case for the `Invalid global constant node` router failure.

### 003 — 2026-08-18, later

**`tri` builds, links, and runs.** First time since 2026-03-20. `tri --help`
prints its full command surface: **144 commands**. Gate: run 32116484331.

Two findings closed it, and both were disguised as something else.

**The gate was answering two questions with one exit code.** `zig build tri` is
a RUN step, so "compiled and then crashed" reported identically to "ninety
compile errors". The first successful link in four months arrived looking like
a failure, and I read past it once. build.zig now has a `tri-compile` step that
installs without running; starting the binary is a separate, non-fatal step.
Whenever a gate covers two questions, the answer to the interesting one is the
one it hides.

**The startup allocation was understated by ~80x.** `CLIState.init` allocated
the TVC corpus unconditionally under the note "~26MB, must be on heap".
`TVCCorpus` is `[10000]TVCEntry`; each entry holds three `HybridBigInt`, each
carrying `unpacked_cache: [59049]Trit` plus an 11810-byte packed buffer —
~213 KB per entry, **~2.1 GB** for the array. The write to `self.count` lands
past it, so every `tri` command, `--help` included, segfaulted before `main()`
did anything. Moved to `ensureCorpus()`, which allocates on first read and
returns null on failure: a machine short of 2.1 GB should lose self-learning,
not the CLI.

**Where the whole repair landed.** From "no build definition exists" to a
running binary: ~20 defects. Thirteen unwired modules, the zig-hdc API drift,
eight separate faults in `sparc/cli.zig`, a `{m}` format specifier, `'●'` in a
`u8`, a module bound to the wrong file of that name, and the 2.1 GB startup
allocation. **Two were mine**, both caught by the gate rather than by me.

**Instrument lesson, twice over.** `-freference-trace=12` named a call site that
had been hidden behind "8 reference(s) hidden"; separating build from run named
a success that had been hidden behind a failure. Both times the fix was to make
the instrument report more precisely, not to look harder at the same output.

**Next.** Verify individual commands actually work (144 of them; `--help`
running proves startup, not function). Then the two benchmark corrections, and
a reduced case for the `Invalid global constant node` router failure.

### 004 — 2026-08-18, night

**Skill written.** `.claude/skills/stale-reference/SKILL.md` — the transferable
half of this repair, in the register of `measurement-discipline`: every rule a
failure that happened. Six instances of "code moved out, reference stayed
behind" tabulated, plus the two mistakes the repair itself made.

**The gate now runs commands, not just builds them.** `--help` proves `main()`
starts and nothing more. Fourteen of the 144 advertised commands are sampled
each build. It found something on the first run:

| | before | after |
|---|---|---|
| `stats` | exit 0, "TODO - not implemented yet" | exit 1 |
| `doctor` | exit 0, "TODO - not implemented yet" | exit 1 |

**Twenty sites** in `tri_commands.zig` printed "not implemented" and returned
normally. A caller could not distinguish work done from work never written —
the same defect as everything else this session, one layer up. They now return
`error.NotImplemented`; the message is unchanged, only the exit code stopped
lying.

**Unexplained, recorded rather than claimed.** `verify` went from exit 124 (a
20-second timeout) to exit 0 between runs, with nothing touching it. Either a
side effect of the lazy corpus, or the command is flaky. Do not attribute this
to the fix without evidence; re-check it next iteration and treat a second
timeout as the real state.

**Still open from the same table.** `fib` and `lucas` print usage and exit 0,
while `phi` in the same situation exits 2 — two conventions in one binary. Not
fixed here because which is correct is a decision, not a repair.

**Third self-inflicted defect.** The mass edit that added the returns put two of
them *before* a trailing print, producing unreachable code. Same shape as the
other two: a uniform edit applied to sites that were not uniform. The parse
check that would have caught it was skipped because the local toolchain had
been cleaned up and CI was "good enough" — it cost a full round.

**Running score: ~20 defects closed, 3 introduced, all 3 caught by the gate
within one cycle.** That ratio is the argument for the gate, not for care.

**Next.** Re-check `verify`. Decide the usage-exit convention. Then the two
benchmark corrections and the router-failure reducer, both untouched since 001.

### 005 — 2026-08-19, night

**I corrected a correction, and the original correction was wrong.**

I told @cavearr by mail, and repeated in commit messages, that the benchmark's
timing column needed fixing because "every openXC7 PASS was against nextpnr's
12 MHz default rather than a real target". Two greps show that is wrong twice
over:

* `--freq` has been passed explicitly since `1437ed5cc`, the commit that
  introduced the workflow. No build here ran on the 12 MHz default.
* The harness emits `synth_ms, pnr_ms, bit_ms, total_ms, cores` and nothing
  else. **There is no timing verdict field**, and the invocation carries
  `--timing-allow-fail`. This half of the benchmark never produced a timing
  column at all.

Written up in `research/benchmark-timing-correction.md`, with what *is* wrong:
the GF designs' XDC (`ax7203_corona.xdc`) contains **no `create_clock`**, so
their only target is `--freq 5.0`; and for blinky the XDC asks 200 MHz while the
flag asks 100 MHz — a 2× disagreement nobody has resolved.

**The lesson, and it is the sharpest of the session.** A correction is a claim,
and it inherits no credibility from being self-critical. Saying "I was wrong
about X" does not establish that X was wrong. I carried a specific-sounding
figure — a named default, a named unit — across three artefacts without opening
the file, because specificity felt like evidence.

Add to the invariants: **before publishing a correction, verify the thing being
corrected, not only the correction.**

**Wall-clock numbers are unaffected.** The harness times three subprocesses;
none of this touches that. What it constrains is what may be said around them.

**Next.** Send the correction to @cavearr and @hansfbaier — it revises something
they were told. Then the router-failure reducer, still untouched since 001.

### 006 — 2026-08-19, night

**Filed openXC7/nextpnr-xilinx#154.** The router failure promised on #114 in
iteration 001 is reduced, controlled and reported.

**It is not an IDDR bug.** Five variants separated the hypotheses; `v4` — a
three-line flip-flop with no IDDR, no I/O primitive and no constant tie —
fails identically:

    ERROR: Invalid global constant node 'INT_L_X0Y98/VCC_WIRE'

**The control is what makes it publishable.** The same design on
`xc7a200tfbg484-2` builds, rc=0. Same `.v`, same image, same commit. So:
part-specific, not a general router defect — and the claim "openXC7 cannot
route a flip-flop", which is what the a35t result alone would have supported,
is false and would have been embarrassing to publish.

**A second defect fell out.** `v2`/`v3` abort rather than error:
`assertion_failure: user.cell->ports.at(user.port).net == ni` at
`common/nextpnr.cc:466`, triggered by IDDR with `CE` from a port. Reported in
the same issue with an offer to split it.

**Fourth self-inflicted defect of the session.** The reducer's first run reused
one XDC across variants that add ports, so four of five died on a missing
IOSTANDARD and never reached the router — reported indistinguishably from a
result. I had guarded against a yosys failure (`rc=20`) and not against a
constraint failure, one commit after writing "a reducer that cannot tell those
apart produces confident nonsense".

**All four of my defects this session have the same shape:** a uniform edit or
a uniform harness applied to sites that were not uniform. Orphaned parameter,
prefix grep, unreachable return, shared XDC. That is a pattern, not four
accidents, and it belongs in the skill rather than the journal.

**One correction to iteration 005.** The 12 MHz figure is real —
`Annotating ports with timing budgets for target frequency 12.00 MHz` appears
in these logs, because this reducer passes no `--freq`. My error was
attributing it to the benchmark harness, which does pass one. The retraction
letter should say the claim was misattributed rather than invented.

**Next.** Add the uniform-edit rule to `stale-reference`. Then `verify`'s
unexplained timeout→0, and the `fib`/`lucas` exit-code convention.

### 007 — 2026-08-19, night

**The re-check instruction paid for itself.** Iteration 004 recorded `verify`
going from exit 124 to exit 0 without being touched, and said explicitly: do not
attribute this to the fix, re-check next iteration, treat a second timeout as
the real state. Third observation: **124 again**.

**And then the explanation removed the defect entirely.** `tri verify` shells out
to `zig build test`:

    const test_result = std.process.Child.run(.{
        .argv = &[_][]const u8{ "zig", "build", "test" },

That legitimately takes minutes. My smoke list gives 20 seconds. So there was no
hang and no flakiness — **my measurement was wrong**: a sample of "pure,
side-effect-free commands" containing one that builds the whole project measures
the build cache, not the command. `verify` is now out of that list, with the
reason written where the list is.

I was one step from filing "verify hangs". The thing that stopped me was the
journal's own instruction to re-check before attributing.

**Skill §11 added.** All four self-inflicted defects share one habit: a uniform
edit applied to non-uniform sites. Three defences, cheapest first: print the
matched lines and read them, assert the expected count, parse-check before
committing.

**Literature review blocked, and left blocked.** Both web tools returned a model
error all iteration. Writing a prior-art section from memory is the exact failure
this project documents, so it is not written. Recorded as blocked-with-reason.

**A repository survey instead**, `research/where-this-work-sits.md`, with its
method bounded in the first paragraph. Two findings worth carrying:

* `f4pga/prjxray` has not been pushed since **2025-06-05** — fourteen months.
  The database the whole ecosystem rests on is dormant, which is why fixes go to
  openXC7's fork and why missing rows need a campaign rather than a request.
* `openXC7/nextpnr-xilinx` is pushed daily and has **one** CI workflow, which
  builds demos. `bit2fasm` appears nowhere in the tree: **no comparison against
  a vendor bitstream runs in its CI at all.**

Four of this month's five defects produced a bitstream that a build-only gate
would pass. That is the gap, stated with sources.

**Next.** The `fib`/`lucas` exit convention (they print usage and exit 0 while
`phi` exits 2). Then propose the part-coverage gate upstream — a three-line flop
across the supported part list would have caught #154 on the day it appeared.

### 008 — 2026-08-19, night

**`fib` and `lucas` stopped reporting a missing argument as success.**
`runPhiCommand`, forty lines above them in the same file, already returned
`exitWithCode(.validation_error)` for the identical situation. Fourth instance
this session of the correct form sitting beside the incorrect one — that is
skill §4, and at four occurrences it is a location rule rather than an anecdote:
**defects live next to working code, in files nothing has exercised.**

**Proposed a part-coverage gate on openXC7#154.** The structural reading of that
defect is that no CI job builds anything on `xc7a35t`, so a part can regress to
totally broken without one red run. One three-line design across the supported
part list, through `fasm2frames` rather than stopping at P&R — because #149
showed a design that places and routes cleanly and then has no bitstream.

Offered to write and test it here before opening a PR, with an explicit
acceptance test for the gate itself: **it must fail on `xc7a35t` and pass on
`xc7a200t` before it is worth anything.** A new gate that cannot reproduce the
defect that motivated it is not evidence.

Asked two questions that are theirs rather than mine — which parts they consider
supported, and per-push versus nightly — and offered the worse fallback of
keeping it here if they would rather not carry another workflow.

**Next.** Build that gate here and demonstrate the acceptance test. Then the
remaining smoke-table anomalies, if any survive.

### 009 — 2026-08-19, night

**The part-coverage gate exists and passes its own acceptance test.**
Run 32122683650:

| part | nextpnr | fasm2frames | result | expected |
|---|---|---|---|---|
| `xc7a35tcsg324-1` | 255 | 1 | fail — `Invalid global constant node X0Y98/VCC_WIRE` | fail |
| `xc7a200tfbg484-2` | 0 | 0 | pass | pass |

Both jobs end "Matches the recorded expectation — gate is sound". It reproduces
openXC7#154 and does not false-positive on a working part, which was the
condition set in iteration 008 before it was worth proposing. Demonstrated on
the issue with an offer to open it as a PR.

**Three properties it was given deliberately**, each from a failure earlier in
this session:

* **It checks itself.** Expectations are pinned per part; a mismatch in either
  direction fails with a different message. A gate that cannot demonstrate it
  still detects something should not be able to report green — the build gate
  spent four months doing exactly that.
* **chipdb/yosys failures are INCONCLUSIVE, not part results.** The first #154
  reducer lacked this and reported four of my own broken XDC files as findings.
* **It runs to `fasm2frames`.** #149 places and routes cleanly and has no
  bitstream; stopping at P&R would call that fine.

**Two parts, not four, and the reason is written in the file.** Verified pins
exist for exactly these two. Guessing pins for the Kintex, Spartan and Zynq
parts would manufacture failures that are mine — the same mistake as the shared
XDC, which is now skill §11. Asked upstream for working pin assignments rather
than inventing them.

**Next.** Whatever upstream answers. Meanwhile: the smoke table is clean apart
from documented stubs, and `verify` is out of it for cause.

### 010 — 2026-08-19, night

**Queue empty, so the deferred item got done.** Upstream has not replied to #154
(every recent comment is mine), and web search still returns a model error — the
literature review stays blocked rather than written from memory, for the second
iteration running.

**`tri journal` added**, the one repeatedly-requested thing that only became
possible tonight. It prints a section of `research/loop-state.md`: latest entry,
invariants, or all. It deliberately parses nothing — a command that *summarised*
the journal would create a second version of the truth, which is the defect
class this session exists to repair.

**Two collisions caught before committing, for once**, rather than by the gate:

* `tri_loop` is already bound to `heartbeat.zig` at main.zig:29, and Zig forbids
  shadowing.
* **`loop` is already a command.** Bare `tri loop` routes to `dev_workflow`
  (main.zig:1532) and CLAUDE.md documents it as pipeline step ten, `tri loop
  decide`. An early dispatch on that name would have stolen it silently — still
  present, still documented, quietly doing something else. Renamed to `journal`.

That is §11 working on the first attempt. Not entirely: the rename's `sed`
matched one usage line of three and I read only the line I aimed at, leaving two
stale references inside the file about stale references. Fixed in a follow-up.

**Exit conventions are now consistent.** `phi`, `fib`, `lucas` all exit 2 on a
missing argument; `stats` and `doctor` exit 1 as unimplemented stubs; the other
seven exit 0 with real output. The smoke summary said "of 13 sampled" while
listing 12 — removing `verify` never decremented the count. Corrected.

**Next.** Nothing queued that does not depend on someone else. If upstream
answers #154, adapt the gate to their part list. Otherwise the honest options
are: extend part coverage once pins are confirmed, or stop adding and let the
gates run.
