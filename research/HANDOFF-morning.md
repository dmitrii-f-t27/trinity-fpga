# What needs a person — hand-off

Written at loop iteration 031, after three consecutive iterations with no
external change. Everything that could be done without a decision has been.
This file exists so acting takes minutes rather than a search through a long
conversation.

---

## 1. Push `zig-golden-float` — five minutes, unblocks strangers

`git clone --recursive` **fails for everyone**, including you on a new machine.
The tree pins `external/zig-golden-float` at gitlink `c7af4bbe`, which is not on
the remote; local checkouts hold `1923572c`, which is not on the remote either.

```bash
cd /Users/playom/trinity-fpga/external/zig-golden-float && git push origin HEAD
```

Then, in the parent repo, commit the gitlink so it names something fetchable.
Until this happens, the numerical core exists only on machines that already have
it — which includes no CI runner and no collaborator.

---

## 2. The #114 board experiment — the last standing hypothesis

Site configuration is **eliminated**. Vendor goldens showed the entire emission
difference at the IDDR site is four `IFF.ZSRVAL_Q` bits that a design with `R`
and `S` tied low should never load. That is reasoning, not measurement, and it
needs the AX7203.

**No rebuild of nextpnr required.** The edit is at FASM level:

```bash
grep -c 'ZSRVAL_Q' design.fasm && grep -v 'IFF.ZSRVAL_Q' design.fasm > design_nozsrval.fasm
```

Then assemble both and flash A/B/A:

```bash
docker run --rm -v "$PWD:/w" regymm/openxc7 bash -c 'source /prjxray/env/bin/activate; for f in design design_nozsrval; do fasm2frames --part xc7a200tfbg484-2 --db-root /nextpnr-xilinx/xilinx/external/prjxray-db/artix7 /w/$f.fasm > /w/$f.frm && xc7frames2bit --part_name xc7a200tfbg484-2 --frm_file /w/$f.frm --output_file /w/$f.bit; done'
```

**Reading the result.** If capture starts without those bits, the cause is found
and the nextpnr fix is small — make the `ZSRVAL` loop conditional on the `SR`
port actually being driven. If capture stays dead, the hypothesis is closed and
the emission space is exhausted: the cause is then clock routing into the ILOGIC
or the ILOGIC itself, not site configuration.

Either outcome is publishable. Check `sudo -n true` first — NOPASSWD does not
survive a reboot.

---

## 3. Two decisions that are yours, not urgent

**The 395 unreachable files.** `research/src-tri-reachability.md` measures them;
the ratchet stops the count growing but deletes nothing. Some may be someone's
unfinished work. A one-pass static analysis is not grounds for removing 3 MB.

**Risky commands in CI.** Smoke coverage is 18 of 144. The rest need either
subcommand invocations with valid arguments, or a decision that commands like
`deploy`, `serve` and `clean` may run on a runner. I judged the static safety
classifier unsound and abandoned it — see skill §12.

---

## 4. Waiting on other people, for reference

| who | what | where |
|---|---|---|
| @hansfbaier | differential-clock question; whether to take the coverage gate as a PR | openXC7/nextpnr-xilinx#154 |
| @cavearr | fuzzer `047b` — without those rows a BUFR from a pin has no bitstream at all | #149 |
| either | whether to regenerate 6 of 8 `demo-projects` goldens so #120 can merge | #120 |

---

## 5. Unsent drafts in the scratchpad

Two letters were written and not sent, because sending is yours:

* the retraction of the timing-column correction — I told them nextpnr's 12 MHz
  default applied to the benchmark harness; it does not, the harness passes
  `--freq` explicitly and emits no timing verdict at all;
* the upstream status letter carrying #154, the coverage gate and the three
  questions.

Both are in the session scratchpad. The retraction matters more than the
status — they may have already acted on a claim of mine that was wrong.
