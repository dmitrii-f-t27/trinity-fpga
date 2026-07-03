# Next-loop checklist — EPIC #199 melt continuation (2026-07-03)

Tight, executable continuation of `LOOP_REPORT_2026_07_03_takum64_routing.md`.
Read that first for the why; this file is the what/which-command.

## State at session end
- 4 commits on `main`: `9ff4e7ea8` (docker retry), `b537d0336` (takum64 opt+fix),
  `399bb0cf8` (takum32 fix), `e7597710c` (report).
- 4 CI runs in flight (see report §7 table).

## Step 1 — watch the decisive run (block on this first)
```bash
gh run watch 28651683990        # TAKUM64 optimized, head b537d033
gh run view 28651683990 --log   # then inspect
```
- **If conclusion = success** → artifact `corona-decode-takum64-bitstream` built.
  Go to Step 2.
- **If failure** → check which step:
  - step 3 (docker pull): should not happen now (retry in place); if it does,
    Docker Hub is having a long outage — wait, don't change code.
  - step 4 (Yosys): unexpected (local iverilog passed); grab the error.
  - step 7 (nextpnr): if `::error::no clean seed` → the 94+72-bit datapath
    *still* doesn't route. Go to Step 4 (deeper optimisation).

## Step 2 — flash + Tier-E proof (only if 28651683990 succeeded)
```bash
# download bitstream
gh run download 28651683990 -n corona-decode-takum64-bitstream -D /tmp/tk64
BIT=/tmp/tk64/build/corona_decode_takum64/corona_decode_ax7203.bit
shasum -a 256 "$BIT"   # record this for the #199 post
# flash (NOPASSWD must be live; re-enable if not — HANDOFF §infra)
sudo -n /opt/homebrew/bin/openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
  -c "init" -c "pld load 0 $BIT" -c "runtest 200000" -c "shutdown"
# host conformance
python3 conformance/takum64_decode_conformance_ax7203.py --n 64
```
- **64/64 bit-exact** → post Tier-E proof to #199 (run ID + SHA + UART log).
  Tier-E HW **71 → 72** (decode 41 → 42).
- **mismatches** → go to Step 5 (conformance extended).

## Step 3 — repeat for takum32 (run 28651957022, head 399bb0cf)
Same flow. takum32 routing case is easier (87-bit L multiply); if its control
run (28643503442, original) also succeeded, prefer the **fixed** bitstream.
Tier-E **72 → 73** if both green.

## Step 4 — if routing still fails (deeper datapath narrowing)
Reproducible analysis at `/tmp/tk/*.py`. Safe knobs still on the table:
- `ell_keep`: currently 46 (margin 2 above the 44 knee). Can try 44 exactly.
- `flo_keep`: currently 24 — has enormous margin (down to 14 is bit-exact). Drop
  to 16 to shave a few more LUTs.
- `corr_q2` quadratic term: can be dropped to linear-only if precision allows
  (re-run `verify_large.py` after); saves the `corr*corr` multiply.
- Last resort: split `L_Q107` into two narrower multiplies (schoolbook) and let
  yosys place them independently — changes the routing graph structure.
Do NOT drop ell_keep below 44 (23.9% mismatches at 32 for takum32; takum64 knee
is similar). Re-run `iverilog` verification after EVERY change.

## Step 5 — if conformance shows mismatches on HW (extended vector catch)
The 64-vector set is too small. Extend and re-flash:
```bash
# bump conformance to 1000 + boundary sweeps
sed -i '' 's/default=64/default=1000/' conformance/takum64_decode_conformance_ax7203.py
# also seed a dedicated ell~-207 sweep (the subnormal-underflow band)
```
Known residual (NOT in 64-vec set, pre-existing in original too):
`f10c717b9c9a28a7`, `b11d9208973d92ce` — 1-ULP Taylor-correction misses.
Fix hypothesis in report §4 P1.6. Use two-oracle method (`formal/gf_mul_ref_tb.v`
pattern) to localise before patching.

## Step 6 — parallel housekeeping (low-risk, can do while CI runs)
- Triage 8 chronically-failing non-EPIC workflows (report §2.4). For each:
  `gh run view --log-failed`, decide fix vs `continue-on-error` + tracking issue.
- Codify truncation sweep as `tri fpga trunc-analyze <fmt>` (report Option C).

## Do NOT
- Push RTL without local `iverilog` bit-exact verification first (report §5).
- Cancel the control runs (28650506195, 28643503442) — they're useful signals.
- Edit `.sh` files (PreToolUse hook blocks them; use `.py` or `tri` subcommands).
- Transcribe SHA by hand — use `shasum` + sed placeholder (HANDOFF lesson 5).
