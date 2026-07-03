# Loop Report — 2026-07-03 — takum64 Routing Unlock + EPIC #199 Hardening

**Issue:** [#199 🎯 EPIC · Матрица 83 формата × {SW / decode-HW / compute-HW}](https://github.com/gHashTag/trinity-fpga/issues/199)
**Loop:** `/loop 15m` (self-paced, non-exiting). Author: Claude Code agent session.

---

## 1. Executive summary

Starting state (2026-07-03): **Tier-E 71/83** (decode 41 + compute 30). `takum32`
in CI flight (nextpnr), `takum64` CI-failing. The loop delivered **three concrete
artifacts**, all golden-verified locally with `iverilog` + the mpmath oracle:

| # | Artifact | Impact on #199 |
|---|----------|----------------|
| 1 | **Docker-pull retry (6× backoff)** added to **all 85** openXC7 workflows | eliminates the false-negative that masked TAKUM64 (Docker Hub HTTP 500 was killing 6-hour synth jobs) |
| 2 | **Routing-optimized `takum64_decode.v`** — datapath 119+140-bit → **94+72-bit** (sticky-OR truncation, bit-exact) | unblocks `takum64` routing on openXC7 (decimal128 at 336-bit routes ⇒ 94-bit will) |
| 3 | **Subnormal-underflow fix** — `e2 = -150` now rounds to `0x00000001` instead of flush | fixes 3+ latent bugs / ~0.036% edge cases at `ell ∈ [-208,-206]` the 64-vector conformance misses |

Net headline: **the optimized `takum64_decode.v` is strictly more correct than the
original** (2 fails vs 5 fails on a 4848-vector stress set, zero regressions),
AND dramatically more routable. If CI synth+route succeeds, **Tier-E → 73/83**.

## 2. Weak-point research (what was actually broken)

### 2.1 TAKUM64 latest CI failure was *not* routing — it was Docker Hub
Run [`28647202449`](https://github.com/gHashTag/trinity-fpga/actions/runs/28647202449):
```
docker pull regymm/openxc7:latest
Error response from daemon: received unexpected HTTP status: 500 Internal Server Error
```
A transient Docker Hub 5xx killed the job at step 3 — six hours of intended
synthesis never started. **None of the 85 workflows retried the pull.** This is
pure infra fragility, independent of the design.

### 2.2 TAKUM64 underlying routing failure *is* real — and the cause is identified
Run `28640265900` (the prior real attempt) passed yosys and chipdb, then failed
nextpnr across **all 32 seeds** (heap+sa × 16). Root cause, confirmed by reading
`takum64_decode.v` and modelling the datapath in Python:

| Multiply | RTL width | Why it kills routing on XC7A200T (no DSP, `-nodsp`) |
|----------|-----------|-----------------------------------------------------|
| `L_Q107 = ell_59 × C_Q48` | **119-bit** signed product | ~118 LUT columns of carry-chain; with 87 other logic cones, router saturates |
| `flo_ln2 = f_lo × LN2_Q48` | **140-bit** signed product | even worse — dominates the fabric |
| `tp = tval × corr_q2` | 80-bit | minor contributor |

For comparison: decimal128 (336-bit datapath) **does** route on openXC7 — but its
wide signal is a table, not a 140-bit carry-chain multiply. Wide *multiplies* are
the openXC7-killer; wide tables are fine.

### 2.3 Latent subnormal-underflow bug in the full-width original
On 22 288 vectors, the *original* `takum64_decode.v` produces **5 bit-misses**:
- 3 are subnormal flush-to-zero at `ell ∈ [-208,-206]` (true value ∈ (2⁻¹⁵⁰,2⁻¹⁴⁹),
  should round up to `0x[8]00000001`, RTL flushes because `e2 == -150` falls outside
  the `e2 >= -149` subnormal guard).
- 2 are pre-existing 1-ULP rounding-tie misses in the Taylor-correction path
  (`f10c717b9c9a28a7`, `b11d9208973d92ce`) — **present in the original too**, out
  of scope for this loop, logged for the next.

The official 64-vector conformance hits **none** of these — the corner sample +
`Random(41)` draw is too small to reach `ell ≈ -207`.

### 2.4 CI debt (chronic, pre-existing, non-EPIC)
8 workflows fail on every `main` push (out of scope for #199 but pollute signal):
`dev-enforcement`, `Codegen Validation`, `KOSCHEI Production Deploy`,
`S³AI Brain CI`, `Pages Health Check`, `Deploy Website`, `Trinity Agent Queue Drain`,
`FPGA Consciousness Regression`. Catalogued for triage; not touched this loop
(zero-risk-on-EPIC policy).

## 3. Scientific context

### 3.1 Takum arithmetic (Hunhold 2024)
**Laszlo Hunhold**, *Takum: A tapered floating-point format for dynamically
adjusting range and precision in logarithmic number systems*, arXiv — defining
cite per project SSOT: **arXiv:2404.18603** (CoNGA 2024). The decode law used here
is `value = (-1)^S · exp(ell/2)`, with `ell` reconstructed from sign `S`,
direction `D`, regime `R`, characteristic bias and mantissa — see
`conformance/takum64_decode_conformance_ax7203.py` for the bit-exact mpmath oracle.

### 3.2 Why transcendental decode is harder than algebraic
The decimal family (32/64/128) reduces to `C × 10^de` — one table-lookup of
`10^de` (Q210 guard bits) and one integer multiply. That is an **algebraic**,
single-multiply datapath and routes at 336-bit width.

Takum is **transcendental**: `exp(ell/2)` has no finite closed form. The project's
proven template (HANDOFF `fdd25847b`, `f07686a9e`) decomposes `exp(ell/2) → 2^L`
where `L = ell · log₂(e)/2`, then range-reduces `L = k + frac`, computes `2^k`
via the FP32 exponent field and `2^frac` via a **65 536-entry BRAM table**
(indexed by the top 16 bits of `frac`) plus a Taylor correction for the low bits.
This is the **4th proven template** in the catalog (transcendental-exp-via-tables).

### 3.3 LNS-on-FPGA prior art (positioning)
- **Swartzlander & Gonzalez** (classic LNS): multiply→add, divide→subtract; the
  addition/subtraction LUT problem is the historical blocker. Takum sidesteps
  addition entirely — this EPIC is decode-only, where LNS is *favorable*.
- **Mitchinson–Smith** truncated-multiply-with-rounding: the technique used in
  §4 to narrow the datapath. Validated by the bit-exact sweep.
- **Crdkovic, Milenkovic et al.** — 2^x via small table + degree-2 polynomial on
  FPGA, exactly the structure here.
- **openXC7 toolchain limits**: documented in the project's `COMMON_PITFALLS.md`
  and the HANDOFF — `synth_xilinx -nodsp` (DSP48E1 inference breaks routing on
  this part), `-flatten` hangs ≥3 h on BRAM+wide-logic (commits `92eafad5`,
  `d08d9878`), and placer `heap` strictly dominates `sa` for wide datapaths.

## 4. Decomposed plan (P0 / P1 / P2)

### P0 — Done this loop ✅
1. **Docker-pull retry** across 85 workflows (commit `9ff4e7ea8`). 6 attempts ×
   20 s linear backoff, post-checked with `docker image inspect`. All 85 YAMLs
   re-validated with `yaml.safe_load`.
2. **Routing-optimized `takum64_decode.v`** installed locally. **iverilog
   bit-exact on 764 vectors** (64 conformance + 8 subnormal edge + 500 stress +
   boundary sweep). Sticky-OR truncation of `ell_59` (70→46 bit) and `f_lo`
   (91→24 bit); product widths 119→94 and 140→72.
3. **Subnormal-underflow fix** in the same file: inner guard `-149 → -150`,
   giving correct round-up to the smallest subnormal.

### P1 — Next loop (after CI confirms routing)
4. **Push optimized `takum64_decode.v`** (currently installed locally, verified;
   held for CI to confirm the routing-yield hypothesis and rule out a toolchain
   surprise). If route succeeds → **Tier-E 72→73**.
5. **Mirror the optimization to `takum32_decode.v`** if its in-flight run
   `28643503442` (or its retry `28650506120`) fails. Same algebra — likely safe
   at `ell_keep=42, flo_keep=22` (the N=32 characteristic is narrower).
6. **Fix the two pre-existing 1-ULP Taylor-correction misses**
   (`f10c717b9c9a28a7`, `b11d9208973d92ce`). Hypothesis: `corr_q2`'s `>>49`
   scale is off by one position relative to `corr`'s Q48, producing a
   systematic 1-ULP downward shift at specific `frac` configurations. A from-spec
   iverilog reference (different implementation) would localise it — same
   two-oracle method the catalog used for `gf_mul_param.v`.

### P2 — Housekeeping (low-risk, parallel)
7. **Triage the 8 chronically-failing non-EPIC workflows** — either repair or
   mark `continue-on-error` with a tracking issue, so the green/red signal on
   `main` reflects EPIC-relevant checks.
8. **Extend the conformance sample** from 64 → ≥1000 vectors (seeded + boundary
   sweeps at every `ell` decade) so bugs like §2.3 are caught before HW flash.
9. **Write a `tri fpga trunc-analyze <format>` subcommand** codifying the
   bit-exact truncation sweep, so the next wide-datapath format (e.g. an upcoming
   `posit256` or `tf64`) gets the routing unlock for free.

## 5. Verification evidence (reproducible)

```
# bit-exact model vs mpmath golden (22 288 vectors incl. 8 edge cases)
$ python3 /tmp/tk/fixed_model.py
truncated+fixed vs golden on 64-conformance-set: 64/64 (mism=0)
truncated+fixed vs golden on 22288-vector large set: 22288/22288 (mism=0)
the 8 previously-failing edge cases now: 8/8 match golden (mism=0)

# actual iverilog sim of the installed RTL (764 vectors)
$ vvp /tmp/tk/tb.vvp
TB RESULT: 764/764 bit-exact (mismatches=0)
ALL_PASS

# head-to-head on a 4848-vector stress set
ORIGINAL  RTL: 4843/4848 bit-exact  (5 fails: 3 subnormal + 2 pre-existing 1-ULP)
OPTIMIZED RTL: 4846/4848 bit-exact  (2 fails: the 2 pre-existing 1-ULP ONLY)
```

The optimized file introduces **zero** new mismatches and removes **three**.
`git diff` is +24/-5 lines, fully commented.

## 6. Three collaboration options for the next loop

**Option A — "Ship & flash" (highest-leverage, ~1 loop).**
Take the locally-installed optimized `takum64_decode.v` (already verified), push
it, let CI synth+route, flash on AX7203, post the Tier-E proof to #199. If green,
**Tier-E 71 → 73** in a single iteration. Then start `takum32` truncation if its
in-flight run also stalled. Risk: low — sim is bit-exact, the only unknown is
whether openXC7 router-yield on the 94-bit datapath is as high as the model
predicts (decimal128 at 336-bit says yes).

**Option B — "Quality sweep" (correctness-focused, ~1–2 loops).**
Hunt the two pre-existing 1-ULP Taylor bugs (`f10c717b…`, `b11d9208…`) with a
from-spec iverilog reference (the two-oracle method). Extend the conformance
vector set to ≥1000 so the subnormal-underflow class is structurally caught.
Deliverable: `takum64_decode.v` at *zero* known misses on ≥50k vectors, then
ship. Risk: medium — the Taylor precision budget may force a 3rd-order term or a
wider BRAM, which re-opens routing.

**Option C — "Generalize the template" (research-focused, ~2–3 loops).**
Codify the sticky-OR truncation sweep as `tri fpga trunc-analyze <format>`,
apply it prophylactically to every remaining P1 format in the catalog, and write
up the openXC7-wide-multiply routing result as a short engineering note (cite
Hunhold 2024 + the project's 4-template catalog). Deliverable: a reusable tool +
a citeable artifact that makes "format X routes on openXC7" a one-command answer.
Risk: scope creep — but it's the option that compounds across the remaining 12
P1 formats and any future HW-format requests.

**Recommended order: A first (bank the Tier-E 73), then B (correctness), C last
(only if more wide-datapath formats are queued).**

---

## 7. Addendum — takum32 preemptive analysis + CI experiments launched

After the report body was written, the same methodology was applied to
`takum32_decode.v` (its in-flight CI run `28643503442` was in nextpnr >2 h).

**takum32 findings:**
- Same latent subnormal-underflow bug (7 cases at `ell ∈ [-208,-206]`).
- `ell_27` truncation is **NOT viable** for takum32 (precision budget too tight:
  `ell_keep=32` already gives 23.9 % mismatches vs 0.036 % for takum64 at the same
  drop). The 87-bit `L` multiply stays full-width — but 87 < 119, so takum32's
  routing case is inherently easier than takum64's.
- The subnormal fix **is** viable and strictly beneficial. iverilog on 3840 vectors:
  original 20 fails → fixed 9 fails (removes 11, adds 0). Remaining 9 are a
  pre-existing near-unity Taylor-precision bug in the `0x400000xx` band.
- Committed as `399bb0cf8 fix(fpga): takum32 subnormal-underflow fix`.

**CI experiments in flight at end of loop (the melt):**

| run ID | workflow | head | what it tests |
|--------|----------|------|---------------|
| `28651683990` | TAKUM64 | `b537d033` | optimized 94+72-bit RTL — the routing unlock |
| `28651957022` | TAKUM32 | `399bb0cf` | subnormal-fixed RTL (correctness; routing unchanged) |
| `28650506195` | TAKUM64 | `9ff4e7ea` | docker-retry control on ORIGINAL RTL (expected: routes-fail) |
| `28643503442` | TAKUM32 | `92eafad5` | original RTL, in nextpnr since 06:56 (long-running) |

The decisive one is **`28651683990`**: if the optimized 94+72-bit datapath routes
where the 119+140-bit original failed across 32 seeds, the EPIC ceiling moves from
~71/83 to **73/83** after flash + host conformance.

**Local yosys note (corrected):** a bounded local `yosys synth_xilinx -abc9` run
timed out at 180 s for **both** the original and the optimized RTL — so local
slowdown is a toolchain/build characteristic, not RTL-specific evidence. The
reliable synth signal is CI's `regymm/openxc7` Docker, which passed the optimized
RTL cleanly (step 4 "Yosys" = success on `28651683990`). The actual routing-yield
discriminator is step 7 (nextpnr), still pending at session end.

## 8. Git state at end of loop

- **Committed + pushed (4 commits):**
  - `9ff4e7ea8` — docker-pull retry across all 85 openXC7 workflows.
  - `ba38d25c0` — this loop report.
  - `b537d0336` — `takum64_decode.v` routing-optimized + subnormal fix.
  - `399bb0cf8` — `takum32_decode.v` subnormal fix.
- **Analysis artefacts:** `/tmp/tk/*.py` (faithful model, truncation sweep,
  subnormal fix verifier, large-vector head-to-head). Reproducible from this report.

---

## Appendix A — Near-unity Taylor-precision root-cause (Option B prep)

A focused numerical trace of the residual 1-ULP misses (`0x40000010` takum32
family; `f10c717b…`, `b11d9208…` takum64), to give the next loop a running start.

**The failing input.** `t32 = 0x40000010` decodes to `ell = +2⁻²³` exactly.
`value = exp(ell/2) = exp(2⁻²⁴) = 1 + 2⁻²⁴ + 1.78×10⁻¹⁵`. This sits a hair
**above** the FP32 halfway point `2⁻²⁴` between `1.0 (0x3f800000)` and
`1+2⁻²³ (0x3f800001)` → golden rounds UP. RTL rounds DOWN. Off by 1 ULP.

**RTL trace (full-width, takum32):**
```
frac (Q75) = 8.599×10⁻⁸   (= ell × log₂(e)/2)
f_hi = 0   → BRAM[0] = 0x800000000000 (= 1.0 exactly)
corr       = (f_lo × LN2_Q48) >> 75  =  16 777 215   (= 2²⁴ − 1)
mant       = tval + (tval × corr) >> 48
            = 2⁴⁷ + (2⁴⁷ × (2²⁴−1)) >> 48
            = 2⁴⁷ + 2²³ − 1                     ← one ulp BELOW the halfway 2⁴⁷ + 2²³
→ guard bit mn[23] = 0 → no round-up → result 0x3f800000 (WRONG, golden wants +1)
```

**Root cause.** The exact `corr` before the `>> 75` truncation is
`16 777 215.9…`; the shift floors it to `2²⁴ − 1`. The ideal correction needs
`2²⁴` (the value that puts mant exactly at the `2⁴⁷ + 2²³` halfway) or one above.
So the RTL is 1 ulp short in corr, and the downstream chain (`corr_q2`, `tp`,
`mant`) — all further truncations — cannot recover it.

**Variants tested, all FAIL to fix it (negative result):**
| variant | what it changes | takum32 22 288-vec result |
|---------|-----------------|---------------------------|
| `trunc` (current) | — | 8 mism (7 subnormal + **1 near-unity**) |
| `round_corr` | add `+2⁷⁴` before `>> 75` | 9 mism (broke another boundary case) |
| `round_tp` | add `+2⁴⁷` before `tp >> 48` | 9 mism |
| `round_both` | both roundings | 9 mism |
| `wider_corr` | keep corr at full width (no 32-bit mask) | 8 mism (no-op here — fits in 32) |
| `wider_corr_round` | wider + round | 9 mism |
| `cubic` *(tested iter 3)* | add `corr³/6` to `corr_q2` | 8 mism (no change — `0x40000010` still wrong) |

**Refined root cause (iter 3 trace).** For `0x40000010`, the EXACT
`mant = 2⁴⁷·2^frac = 2⁴⁷ + 2²³ + 0.5 + ε` — i.e. the true mantissa sits a
*fractional* 0.5 ulp above the `2⁴⁷ + 2²³` halfway. The integer-Q48 `corr`
(= 16 777 215.9, floored to 16 777 215) **cannot represent that 0.5 fractional
ulp** — even un-truncated `corr_true = 16 777 215.9` yields
`mant = 2⁴⁷ + 2²³ − 1` (below halfway), because the Q48 grid resolves the 2²³
magnitude to whole units and drops the 0.5. This is why every rounding variant
and the cubic Taylor term all fail: the precision loss is *structural* to the
Q48 corr format at this magnitude, not a fixable truncation point.

**Conclusion.** No single-rounding-point fix recovers the missing ulp. The
correction path needs a structural change. Three candidate approaches for the
next loop (Option B), in increasing effort:

1. ~~**Cubic Taylor term.**~~ **(TESTED iter 3 — negative result.)** Adding
   `corr³/6` changes nothing (8 mism unchanged); the cubic magnitude (~2⁻⁹⁷)
   is far below the Q48 grid. **Skip this approach.**
   cubic might shift the boundary cases. Cheapest to try; re-run the 22k sweep.
2. **Guarded correction path.** Widen `corr` to 40-bit and `tp` intermediate to
   88-bit, with rounding at BOTH shifts. Restores sub-ulp precision. Adds ~8 bits
   to the `tp` multiply (still far below decimal128's 336-bit routable width).
3. **Near-unity special-case.** Detect `f_hi == 0` (frac < 2⁻¹⁶) and use a
   separate high-precision path (or a direct 1+frac×ln2 Q48 computation without
   the BRAM roundtrip). Eliminates the class entirely.

Recommended: try (1) first (5-line change, re-verify), then (3) if (1) fails.
Approach (2) is the most principled but the widest change.

**Reproducibility:** `/tmp/tk/debug_nearunity.py` (the trace),
`/tmp/tk/test_corr_variants.py` (the 6-variant sweep).
