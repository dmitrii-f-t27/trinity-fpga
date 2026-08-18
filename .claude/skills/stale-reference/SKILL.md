---
name: stale-reference
description: Repairing a build, tree, or dependency that rotted silently — why extraction leaves dangling references, why a gate that answers two questions hides the interesting one, and the habits that separate a real fix from one that compiles. Use when something has not been built or run in a long time, when a refactor moved code between repositories, or before writing a CI gate.
---

# Stale references, and gates that hide their own news

Distilled from one evening that took a CLI from "no build definition exists" to a
running binary — about twenty defects, **nine of them introduced by the repair
itself** (§11). Every rule below is a specific failure that happened.

The single sentence, if you read nothing else:

> **Code moves out; references stay behind; nothing reports it, because nothing
> runs the build.**

Six independent instances in one tree, all the same shape:

| What moved | Where to | What was left pointing at it |
|---|---|---|
| farm subsystem | `trinity-training` | 20 references to a deleted `local_farm.zig` |
| VSA core | `zig-hdc` | `src/vsa.zig` gone, build still named it |
| physics | `zig-physics` | `quantum_gravity_full` imported by name |
| `src/vsa/*` inside zig-hdc | deduplicated to one copy | callers on the old API arity |
| `build.zig` | renamed to `.tri`, then deleted | every named module unresolvable |
| numerical core commit | never pushed | gitlink to an unfetchable SHA |

None was noticed at the time. All six were found in one evening — by running the
build.

---

## 1. A gate that answers two questions with one exit code hides the interesting one

The build gate ran `zig build tri`. That is a **run** step. So "compiled, linked,
then crashed at startup" and "ninety compile errors" produced the same red.

The first successful link in four months arrived looking exactly like every
failure before it, and was read past once:

```
Build Summary: 1/3 steps succeeded
tri
+- run exe tri failure          <- this is a SUCCESS being reported as a failure
```

**Rule.** One question per gate step, named in the step title. *Does it parse?*
is not *does the graph load?* is not *does it compile?* is not *does it run?*
When a step covers two questions, the one it hides is the one you needed.

Corollary: a run check belongs in the pipeline, but as its own step with
`continue-on-error`, reporting the exit code. A crash is information, not a
build failure.

---

## 2. Fix the instrument before you look harder at the same output

Twice in one evening the right move was to make the tool speak more precisely,
not to stare at what it already said.

* A comptime format error reported `std/Io/Writer.zig:1355` and hid the real
  call site behind `8 reference(s) hidden`. Adding `-freference-trace=12` named
  the line on the very next run. **A log that points at the standard library for
  a defect in your repository is sending the reader to the wrong place.**
* Separating build from run (above) named a success that had been invisible.

**Rule.** When a diagnostic is unhelpful, the first fix is the diagnostic.

---

## 3. Enumerate the defect class; do not iterate one per CI round

Fixing `no module named X` one round at a time costs a full build per defect and
finds them in the compiler's order rather than yours. Enumerating instead:

```
34 named imports under src/tri  →  21 already wired  →  13 missing
```

All thirteen in one commit. Roughly ten CI rounds saved.

**Rule.** If the defect class is enumerable by a script, enumerate it. Iteration
is for classes you cannot list.

---

## 4. The correct form is usually already next door

Four times in one file, the right usage sat a few lines from the wrong one:

* `results.items` used in three places, `for (results)` in a fourth
* `RESET` formatted `{s}` eleven times, `{m}` once
* `totalVelocity` called with seven arguments in `fitting.zig`, eight in `cli.zig`
* `std.json.Array.append` correct everywhere but one call

**Rule.** Before inventing a fix, grep the same file for the same call. Defects
accumulate where the compiler has not looked, and they accumulate *beside*
correct code, which is why they look plausible.

---

## 5. Two mistakes the repair itself made

Recorded because they are the ones a careful person still makes. Two more
followed later in the same session; §11 collects all four and names what they
have in common.

**A prefix match is not an identity match.** `grep 'pub const GoldenChain'`
matched `GoldenChainAgent`, so a module was wired to the wrong file of a
duplicated name. Two files were called `golden_chain.zig`; only one exported the
type. **Grep for the terminator** — `pub const GoldenChain =` or `\b` — when the
name could be a prefix.

**Removing an argument can orphan a parameter.** Dropping an allocator from
`bundle2(...)` left the enclosing function's `allocator` parameter unread, and
the next build failed on that. **After removing an argument, check the enclosing
function still uses its own parameters** — before committing, not one round
later.

---

## 6. The cheaper repair is not always the smaller change

`row_buffer[x] = '●'` fails because U+25CF does not fit a `u8`. Swapping it for
`'*'` compiles immediately — and silently downgrades the output.

Reading further showed the print loop already emitted the glyph as a string
literal and only used the buffer as a marker. So markers were the correct fix,
the rendering was untouched, and nothing was lost.

**Rule.** When a type error has an obvious narrowing fix, check what the value is
actually *for* first. A compile error converted into a silent behaviour change is
worse than the compile error.

---

## 7. Comments about size and cost drift; measure them

```zig
// Heap-allocate TVC corpus for self-learning (~26MB, must be on heap)
```

It was **~2.1 GB** — `[10000]TVCEntry`, each holding three `HybridBigInt` with
`[59049]Trit` caches. Understated by about eighty times. Allocated
unconditionally at startup, so every command including `--help` segfaulted
before `main()` did anything.

**Rule.** A comment stating a size is a claim with no test attached. If the
number matters, compute it from the type — `@sizeOf` is available at comptime —
or do the arithmetic explicitly in the commit that relies on it.

---

## 8. Restoring from history: pick the last version that *parsed*

`build.zig` had been unparseable since a specific commit, then edited by **73
further commits**, then renamed away and deleted. Two executable declarations
had lost their opening lines.

Restoring the newest version means reconstructing code nobody ever ran.
Restoring the last version that parsed loses only edits that were never
validated — because a file that does not parse cannot have been.

**Rule.** `git log --all -- <file>` plus a parse check on each revision finds the
last good one in seconds. Prefer it to repairing damage of unknown provenance.

---

## 9. Dependency pins to a branch are not pins

```
.zodd = .{ .url = "git+https://github.com/CogitatorTech/zodd#main", ... }
```

`#main` moved from alpha.3 to alpha.6, the new version required a different
compiler, and the build broke with no change in the repository. A sibling
dependency's hash was the literal placeholder `????????????????????????????????????????`
— it could never have resolved.

**Rule.** Pin dependencies to commits. A hash that has never been filled in is a
dependency that has never been fetched, and something else is quietly supplying
those symbols — or nothing is, and the code using them has never been compiled.

Also: **check whether the dependency is used at all.** Three of four declared
here were referenced nowhere in the build and were breaking it for nothing.

---

## 10. What to do first, in order

1. Run the build. Not "read the build" — run it.
2. Ask what the failure actually says. If it names the standard library, improve
   the trace before theorising.
3. Split any gate that covers more than one question.
4. Enumerate the defect class before fixing an instance of it.
5. For each fix: does the correct form exist nearby? does removing this argument
   orphan something? is the cheap fix a silent downgrade?
6. Record what was left deliberately unfixed and why. "Not in the module graph,
   so nothing has compiled it against this signature" is a reason; "looked fine"
   is not.

---

## 11. The uniform edit is the repair's own failure mode

Nine defects were introduced by the repair in one session. All nine are the
same mistake, and with a sample that size it can be stated precisely:

> **A rule that holds for every case you looked at, applied to a set containing
> a case you did not.**

| the edit | what it assumed | what bit |
|---|---|---|
| dropped an argument from every `bundle2` call | the callers were alike | one enclosing function stopped using its parameter |
| `grep 'pub const GoldenChain'` | the name was unique | it matched `GoldenChainAgent` by prefix |
| appended `return` after every stub print | the stubs were alike | two had a second print after it, now unreachable |
| one XDC for five reducer variants | the variants had the same ports | four had extra ports and never reached the router |
| rewrote calls on anything not ending `_mod` | modules follow that naming | `wasm_root` is a module and does not |
| one `--db-root .../artix7` for every part | the parts share a family | a spartan7 part is not in the artix7 database |
| widened a classifier to catch assembler errors | a missing FASM means a harness fault | after a failed P&R it means the failure the gate exists to detect |
| took a part's speed grade from the board supplying its pins | one source is one source | the database that answers about it ships a different grade |

Not seven accidents. One habit, and note where the exceptions live: never in
the sites that motivated the edit, always in the ones adjacent to them. The
`_mod` heuristic was derived from every module I had read; `wasm_root` was the
one I had not. The `artix7` db-root was right for both parts in the matrix at
the time it was written.

The script that edits N places is the fastest tool available and the one most
likely to be wrong, because its speed comes precisely from not looking at the
places. Three cheap defences, in order of value:

1. **Print what you are about to change, with context, and read it.** All four
   would have been visible in a diff of the matched lines.
2. **Assert the count.** If the change should touch twenty sites, say twenty and
   fail if it is nineteen or twenty-one.
3. **Parse-check before committing.** Available every time; skipped once because
   the local toolchain had been cleaned up and CI was "good enough". That saved
   a minute and cost a full round.

The general form, which is the same rule as §4 seen from the other side: the
sites that look alike enough to edit mechanically are exactly the sites nobody
has read recently.

### The matrix corollary

A CI matrix is the same trap wearing different clothes. One workflow in this
repository baked in a per-part value **three separate times** — the IOSTANDARD
(`LVCMOS33`), the database root (`artix7`), and the part's speed grade — and
each was correct for every row present on the day it was written.

> **A matrix with N rows teaches you nothing about the N+1th, and the values
> most likely to be hardcoded are exactly the ones the current rows happen to
> agree on.**

The defence is cheap and worth applying before adding any row: for each literal
in the shared code path, ask which row would have to change for this to be
wrong — and if you cannot name one, that is because you have only looked at the
rows that agree.

And when a row is added, one more habit: **take every field of an identifier
from the same source.** The speed-grade defect came from reading a part's pins
off a board file and its name off the same file, when the database that would
be asked about it ships a different grade.
