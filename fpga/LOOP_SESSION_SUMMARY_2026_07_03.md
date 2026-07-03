# Loop session summary — 2026-07-03 — EPIC #199

**Read this first.** Single-page consolidation of the full /loop session (13
iterations, 22 commits). Points to the detailed docs below.

## Headline result

- **lns16 decode-HW correctness fix COMPLETE**: bitstream built (CI run
  `28668900768`, GREEN), `--extended` conformance ready. Flash + Tier-E pending
  HW access. lns16 goes from "Tier-E-proven-with-10.7%-latent-error" to
  "Tier-E-proven-and-actually-correct".
- **takum32/64 routing-optimized + subnormal-fixed**: committed, verified
  iverilog bit-exact; CI routing resolution still pending (per-seed timeout
  installed to convert 6h hangs into definitive route/clean-fail answers).
- **No catalog-wide subnormal-flush bug** (an earlier "6 suspects" claim was
  retracted honestly — all 6 goldens flush too; lns16 is the sole confirmed case).

## Commits by category (24 total, chronological within each)

### RTL correctness fixes (5)
- `b537d0336` takum64 routing-opt (119+140→94+72-bit) + subnormal (e2=-150)
- `399bb0cf8` takum32 subnormal fix (e2=-150)
- `12850fc7a` takum32 routing-opt (107→72-bit f_lo)
- `bffc7a2ab` lns16 subnormal-rounding (flush→1-ULP, 5× reduction)
- `89135c37e` lns16 yosys-compat (module-level regs) → **CI GREEN bitstream**

### Infrastructure (3)
- `9ff4e7ea8` docker-pull retry (6× backoff) across all 85 openXC7 workflows
- `5b6878ebb` per-seed 30min nextpnr timeout (first attempt — outer `timeout docker run`)
- `6448ae520` **per-seed timeout INSIDE container** (`--signal=KILL` on nextpnr) — the
  outer wrapper didn't propagate SIGTERM into the container, so the first attempt
  was ineffective (takum CI stuck 6.5h). This is the working version.

### Conformance methodology (2)
- `5e63b519a` takum32/64 `--extended` (subnormal band) + `--strict`
- `776c4f504` lns16 `--extended` (completes the lns16 verification cycle)

### Reusable tools (2)
- `8e5c131fb` `tools/fpga_trunc_analyze.py` — bit-exact truncation sweep (takum32/64 registered)
- `de4f0eab4` `tools/fpga_subnormal_audit.py` — catalog flush-bug scan with golden-cross-check

### Documentation (7+)
- `ba38d25c0` LOOP_REPORT (main, with Appendix A near-unity)
- `e09f0a5d7` NEXT_LOOP_CHECKLIST (executable, with yosys-compat lesson)
- `31f0ffc0e` FINDING lns16 subnormal-flush
- `6035ac427` FINDING catalog audit
- `b044c7ef6` **RETRACTION of catalog audit** (honest science)
- `80816689a`, `321aae34b`, `e452f4a3c`, `30a53a81e`, `e7597710c` (refinements)

## CI state at session end

| run | head | result | meaning |
|-----|------|--------|---------|
| `28668900768` lns16 fixed | `89135c37` | **SUCCESS** ✅ | bitstream ready for flash |
| `28670353297` TAKUM64 opt | `6448ae52` | in_progress (step 4) | inner-SIGKILL timeout will resolve |
| `28670353291` TAKUM32 opt | `6448ae52` | in_progress (step 4) | inner-SIGKILL timeout will resolve |
| ~~`28666152468`/`28666152309`~~ | `5b6878eb` | cancelled | broken outer-timeout; superseded |

## Exact next actions (priority order)

1. **takum routing** — `gh run view 28670353297 --json conclusion` (inner-SIGKILL-timeout run):
   - `success` → download artifact → flash → `--extended` Tier-E → **decode-HW 71→73/83**.
   - `failure` (clean `::error::no clean seed`) → openXC7 cannot route the takum
     BRAM+wide-multiply structure even at 94+72-bit. Strategic choice: accept
     HW-ceiling ~71/83, or try Vivado (license-required, off-mission for openXC7).
2. **lns16 flash** (needs HW access) —
   `gh run download 28668900768 -n corona-decode-lns16-bitstream` → openocd flash →
   `python3 conformance/lns16_decode_conformance_ax7203.py --extended` → post Tier-E.
3. **Near-unity polish (Option B, optional)** — approach (2) wider correction path
   for takum32/64 + lns16 subnormal 1-ULP residual. Gated on routing confirmation
   first (don't widen the datapath before routing is proven).

## Key lessons (for future loops)

1. **iverilog is necessary but not sufficient** — yosys is stricter on
   SystemVerilog features (block-local regs). Always run `yosys -p synth_xilinx`
   locally before pushing RTL. CI's yosys step doesn't fail on error → malformed
   JSON → nextpnr instant crash → misleading "no clean seed".
2. **RTL-pattern-only audits over-claim** — must cross-check the golden's
   behavior. The "6 subnormal-flush suspects" were all clean (golden flushes too).
   lns16 was the sole real bug. `fpga_subnormal_audit.py` now does this check.
3. **openXC7 routing on BRAM + wide multiplies is the constraint** — decimal128
   (336-bit TABLE) routes fine; takum (119-bit MULTIPLY) didn't. Sticky-OR
   truncation is the proven unlock (codified in `fpga_trunc_analyze.py`).
4. **CI hang diagnosis** — a run "in_progress" for 6h on a small design is
   nextpnr hanging on seed 1 (not genuine routing failure). Per-seed timeout
   converts it to a definitive answer.

## Detailed docs (in fpga/)
- `LOOP_REPORT_2026_07_03_takum64_routing.md` — main report + Appendix A (near-unity)
- `NEXT_LOOP_CHECKLIST_2026_07_03.md` — executable step-by-step
- `FINDING_2026_07_03_lns16_subnormal_flush.md` — lns16 bug detail + fix template
- `FINDING_2026_07_03_catalog_subnormal_flush.md` — catalog audit + RETRACTION
