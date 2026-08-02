# Tier-E, with the numbers a reader can re-derive

Everything below is produced by `research/measure_tier_e_cells.py`, which defines a
Tier-E cell in code rather than counting by hand. Run it and you get this table. The
figures carry a date — the issue grows, and every count grows with it.

> Measured 2026-08-02 against `gHashTag/trinity-fpga#199`, 224 comments.

---

## What changed, and in which direction

The checklist's §4c has carried these numbers since pass 91. Three of the four are
**under**-claims and one is an **over**-claim.

| | as written | measured | direction |
|---|---|---|---|
| comments carrying all four links | 74 | **75** | issue grew |
| cells covered | 45 | **72** format-operation pairs, over **49** distinct formats | under |
| of the 83 published packs | 44 (53 %) | **46 (55 %)** | under |
| compute proofs | 30, across **12** formats "gf4–gf32, `double_double`, `quad_double`" | 30, across **10** formats — **gf4–gf32 only** | **over** |

The last row is the one to fix first. `double_double` and `quad_double` carry **decode**
proofs, not arithmetic ones. Decoding a bit pattern on silicon and adding two values on
silicon are different claims, and the sentence currently merges them.

The 44 → 46 correction is a naming reconciliation, made against pack **metadata** rather
than name similarity: the Tier-E cell `bf16` is the pack `bf16_golden`, whose metadata
declares `format: BFLOAT16`; the cell `mxfp8_e4m3` is the pack `mxfp8`, whose catalogue
entry declares `bits=8, e=4, m=3`.

---

## The correction that matters most: `takum32` had no hardware evidence

The `with_hardware` list carried **`takum32 65536/65536`**. Two things are wrong with
that, and the second explains why the first survived.

**No comment in issue #199 carries a complete four-link chain for takum32.** Thirteen
mention it; none qualifies. The issue states the verdict in its own words:

> takum64/32 **synthesize** on Artix-7 200T (XC7A200T) but do **not route**.
> Per rule #1 (Tier E only with full 4/4 chain) and anti-fake-pass, takum is **NOT** Tier E.
> Honest achievable HW ceiling on AX7203 = 71/83.

Both CI runs finished `conclusion=failure` at the four-hour per-seed timeout, all eight
seeds unrouted. **There is no bitstream, so there can be no flash and no UART log.**

**And the number belongs to `gf16`.** The only takum32-mentioning comment that contains
a `HW RESULT` line reads `HW RESULT: 65536/65536 bit-exact (fails=0) — all 65536 gf16
codes`. The figure was transcribed onto the wrong row.

That also explains the pass-148 finding. takum32 was named as one of two formats
"exhaustive over the whole code space" at 65,536 codes — which is 0.00153 % of a 32-bit
space. **It was never a takum32 measurement at all.**

A reviewer who opened #199 would have found the verdict before finding the claim. This
row must come out before submission.

Two rows move the other way: **`tf32` and `mxfp8`** each carry a complete four-link
chain and were listed as software-only — `mxfp8`'s proof reads
`HW RESULT: 1056/1056 bit-exact`. Net: 45 with hardware becomes **46**, 38 software-only
becomes **37**, and 46 + 37 is still 83.

---

## Replacement paragraph — Paper B, hardware section

> Hardware evidence is held to a standard we call **Tier-E**, and it is stated so that a
> reader can check it. A cell qualifies only when its published proof carries **all
> four** of: a public openXC7 CI run with its URL, the SHA-256 of the specific bitstream,
> a UART log reading `HW RESULT: N/N bit-exact (fails=0)` at 160000 baud from the
> physical board, and a matching IDCODE `0x13636093`. A green commit message does not
> count; a passing simulation does not count.
>
> Of the 224 proof comments published in `trinity-fpga#199`, **75 carry all four links**.
> They cover **72 format-operation cells over 49 distinct formats**, of which **46 map
> onto packs in this catalogue — 46 of 83, or 55 %, with decode verified on the physical
> board.** Two are exhaustive over the whole code space: `binary16` and `gf16`, at
> 65,536/65,536 each.
>
> **Arithmetic is a smaller and separate claim.** Thirty compute proofs cover ten
> formats — `gf4` through `gf32` — for ADD, MUL and SUB. Decoding a bit pattern on
> silicon and performing arithmetic on silicon are different claims, and we do not
> combine them.
>
> Three formats carry Tier-E proofs without a pack in this catalogue — `bitnet`, `e8m0`
> and `mxint8` — so the hardware track is slightly wider than the catalogue rather than
> a subset of it.
>
> The 37 software-only packs are a coherent set rather than a gap in rigour: the wide GF
> rungs, the wide integers, `x87_fp80`, and the parametric entries with no fixed layout
> to synthesise.

---

## One caveat that belongs in the same paragraph

One of the qualifying proofs is **partial and should be described as such**. `lns16`
decode reports `472/576 bit-exact, 104 known-limitation(s), 0 hard-fail(s)`, where the
104 are 1-ULP subnormal-band residuals, tagged in the log and documented in an appendix.
Counting it on zero hard-fails is defensible and the proof says so openly — but a paper
quoting "75 proofs" should not imply all 75 are uniformly `N/N`.

Those residuals are also the campaign's third independent sighting of the same boundary.
`takum32` differs from libtakum by one ULP because a logarithmic decode needs `exp()`,
and numpy documents 1–4 ULP tolerances for the same reason. Software oracle, third-party
library and silicon agree: bit-exactness is attainable over the decidable class, and
logarithmic evaluation is not in it.

---

## Why the numbers moved at all

They were counted by hand once, and "cell" was never defined. `measure_tier_e_cells.py`
now defines it — four link patterns and a title pattern — and `--self-check` exercises
each one **both ways**: that it fires on a complete proof, and that it stops firing when
that link is removed. A count that nobody can recompute is a transcription; this one is
a measurement, and it will move again as the issue grows.
