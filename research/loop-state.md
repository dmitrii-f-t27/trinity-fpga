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
