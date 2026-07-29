# Wave-Loop v2 — Iteration Playbook (every 15 min)

> Canonical SOP for each Wave-loop run. Preserves session outcomes
> from 2026-06-26 (AX7203 FPGA diagnostics). Cron: `*/15 * * * *` (session-only).

Each step = INPUT → ACTION → GATE. Gate not passed → stop. Language = Russian, Vasilev romanization.

## §0 Goal: "flash the full catalog"
- **SSOT** = `gHashTag/t27/formats_catalog.t27` (PR #1028), NOT in trinity-fpga.
- **COUNT = 83** [verified HEAD t27: INDEX_all_formats.json total_formats=83, total_packs=83, bitexact_packs=55, structural=22, selfconsistent=6]. 84=arXiv erratum; 80/77=outdated Corona ROM snapshots.
- Bit-exact packs exist for **6**: GF16, MXFP4elem, BF16, FP8 E4M3, FP8 E5M2, E8M0.
- **Corona** (`gHashTag/tt-trinity-corona`) = read-only oracle GF180/TTGF26b: REUSE `formal/fv_*.sv` (formal equivalence > vectors) + `post_silicon/corona_vectors.py` (generator, op+a+b→result protocol); 17 Tier-1 RTL decoders, the rest ROM; **≠ AX7203-compute** (different primitives/timing — we reuse logic+FV, not bitstreams).
- Three goals: SW-conformance (6→all), HW-conformance (FPGA bit-exact via `/dev/cu.usbserial-120`), Multi-width RTL (GF4–GF256).
- Milestone: the matrix **[format × {SW✓, FPGA✓}]**.

## §1 GATE-0 — context/honesty
Memory + HEAD/PR/watchdog + previous loop's gates.

## §2 Step 1 — audit (gh, BOTH repos)
trinity-fpga (FPGA) + gHashTag/t27 (catalog) + tt-trinity-corona (oracle) → registry of TECH/SCIENTIFIC/LEGAL/STRATEGIC × P0/P1/P2.

## §3 Step 2 — scientific review 2025–2026
Lean/Coq/Flocq, ZKML, GreenAI, ternary FPGA/ASIC, Sail ISA. ≥1 source/line or "nothing new".

## §4 GENERAL's CRITIQUE (mandatory)
- Fact-check of constants.
- "Works" → via which channel? **Camera = RETIRED** (Nyquist 2.5 Hz, bank outside FOV) — only **electrical discriminator**.
- **necessary ≠ sufficient**: "clock oscillates" ≠ "fit for UART/gf16".
- **workaround ≠ fix**: seed-search, --force, default port = workarounds.
- One unknown per test.

## §5 Step 3 — plan
`implementation_plan`, statuses [DONE]/[IN LOOP]/[REQUIRES USER]/[NEXT LOOP], P0/P1/P2, which matrix cells it closes.

## §6 Step 4 — implementation
- CAN DO: RTL/XDC/CI (**STANDARD: seed-search 1..8 + routing-guard grep "Failed to find a route", WITHOUT --force**) + harness + decoder (self-test) + paper/PDF + erratum RU+EN + branch/PR + flash/UART (self).
- **Push = confirm_action.**
- Methodology: one-unknown; CDC multi-bit → Gray; dual-nibble electrical discriminator (ref+test nibble); exact-byte echo (0x55=baud+wire OK; 0x57/0x51=baud-err; silence=wire dead).
- Flashing: `openocd -f ax7203_al321.cfg -c init -c "pld load 0 …bit" -c "runtest 200000" -c shutdown`; **IDCODE-recheck 0x13636093** after each.

## §7 Step 5 — report + 3 collaboration options
`otchet_wave_loop.md` → PDF (`share_file should_validate=false`). Summary/registry/review/plan/matrix/3 options (low-medium-high risk) + recommendation.

## §8 Final — update skills
New truths → `fpga-hardware-truth.md` + this playbook; durable → memory.

---

## FPGA-TRUTHS [verified 2026-06-26]
- AX7203 = XC7A200T-2FBG484I (`xc7a200tfbg484-2`), IDCODE **0x13636093**.
- LED B13/C13/D14/D15 = **LVCMOS18** (LED1-4, 1-based; **silkscreen-label NOT verified**).
- rst **T6 LVCMOS15** active-low.
- UART TX=**N15** / RX=**P20** (LVCMOS33) → CP2102N **`/dev/cu.usbserial-120`** (**TX+RX PROVEN alive**); AL321 ch.B (`/dev/cu.usbserial-210512180081`) = **DEAD**.
- 200 MHz R4/T4 DIFF_SSTL15→IBUFDS→BUFG (raw, no PLL): counter is alive [**23.7/s, proven**], **BUT UART at 200 MHz does not respond** (gf16+loopback = 0) — **necessary≠sufficient**.
- **CFGMCLK (STARTUPE2) ≈ 69–70 MHz [measured] = PROVEN clock** (all CFGMCLK designs work).
- **Camera = RETIRED.** Only electrical discriminator.
- **BAUD_DIV = host baud**: CFGMCLK designs ~160000, 200 MHz designs ~115200.
- **CI: seed-search 1..8, WITHOUT --force** (--force ships broken `$PACKER_VCC_NET` bitstreams).

## Honesty checklist
- No "first/best" → [proven]/[measured]/[open hypothesis]/[requires confirmation].
- Catalog = 83 (pending t27 HEAD reconciliation).
- 49× energy efficiency = [hypothesis].
- φ²+φ⁻²=3 = identity-witness.
- FPGA push = confirm_action.
