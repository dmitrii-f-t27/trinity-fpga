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
