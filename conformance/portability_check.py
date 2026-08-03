#!/usr/bin/env python3
"""Synthesise the TRI-NET node for every FPGA family this yosys can target.

The check asserts an invariant rather than a number.

  * Every family must recover the SAME amount of sequential state. Measured
    2026-08-03 across ten families under yosys 0.62: 1082 flip-flops on nine of
    them, 1092 on Intel ALM, whose register cell absorbs reset logic the others
    express separately. Ten independent synthesisers agreeing to the register is
    what portable RTL looks like; a design tuned to one vendor's carry chain
    would not survive the transfer.

    (It was 819 on 2026-08-02, before the receipt key started arriving over the
    wire and brought a key register and its write-once latch with it. The number
    is not the claim — the agreement is — which is why this check asserts the
    spread and not the value.)

  * No family may infer a multiplier. The dot product is
    popcount(agreements) - popcount(disagreements), so there is no multiply to
    find. On Xilinx this is enforced with -nodsp because DSP48 inference caused
    a routing failure once; the point of checking the other eight, which get no
    such flag, is that they decline on their own.

  * The LUT count is deliberately NOT asserted. It ranged 939..1737, and that
    spread is LUT width and carry architecture doing their job.

A tolerance is allowed on the flip-flop count because register cells legitimately
absorb different amounts of surrounding logic per family. It is small on purpose:
a real regression -- a lost pipeline stage, an optimised-away buffer -- moves the
count by far more than a packing difference does.

Author: Dmitrii Vasilev (@gHashTag)
"""

import argparse
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES = [
    ROOT / "fpga" / "portable" / "trinet_node_core.v",
    ROOT / "fpga" / "openxc7-synth" / "trinet_siphash24.v",
]
TOP = "trinet_node_core"

# Xilinx needs its two flags for reasons recorded in the FPGA skill: -nodsp
# because DSP48 inference for GF multiply caused a routing failure, and -nocarry
# because nextpnr-xilinx does not handle the inferred carry chains.
EXTRA_ARGS = {"xilinx": "-flatten -nocarry -nodsp -arch xc7"}

FF_PAT = re.compile(
    r"dff|_FF\b|FD[RCPS]E?\b|FD1P|MAP_SEQ|EFX_FF|TRELLIS_FF|MISTRAL_FF", re.I)
LUT_PAT = re.compile(r"lut|ALUT|MSLICE|SLICE", re.I)
MUL_PAT = re.compile(r"dsp\d|mult|MULT18|DSP48", re.I)
SKIP_PAT = re.compile(r"wire|port|cell|memor|process|submod", re.I)

# Families whose synth_ pass exists but which are not general-purpose FPGA
# targets, or which need a device argument to run at all.
EXCLUDE = {"ice40up5k", "coolrunner2", "greenpak4", "quicklogic", "fabulous",
           "gowin_", "intel", "lattice", "machxo2", "sf2", "microchip"}


def available_families() -> list:
    out = subprocess.run(["yosys", "-h"], capture_output=True, text=True).stdout
    out += subprocess.run(["yosys", "-H"], capture_output=True, text=True).stdout
    fams = sorted({m.group(1) for m in re.finditer(r"\bsynth_(\w+)\b", out)})
    return [f for f in fams if f not in EXCLUDE]


def synth(family: str, workdir: pathlib.Path):
    extra = EXTRA_ARGS.get(family, "")
    reads = "\n".join(f"read_verilog {s}" for s in SOURCES)
    script = workdir / f"{family}.ys"
    script.write_text(
        f"{reads}\nhierarchy -top {TOP}\n"
        f"synth_{family} {extra} -top {TOP}\nstat -top {TOP}\n")
    r = subprocess.run(["yosys", "-s", str(script)],
                       capture_output=True, text=True, timeout=900)
    return r.returncode, r.stdout + r.stderr


def parse(log: str) -> dict:
    """Cell counts from the last per-module stat block for the top."""
    block = log.split(f"=== {TOP} ===")[-1].split("=== design hierarchy ===")[0]
    cells = {}
    for line in block.splitlines():
        m = re.match(r"^\s+(\d+)\s+(\$?[A-Za-z][\w$]*)\s*$", line)
        if m and not SKIP_PAT.search(m.group(2)):
            cells[m.group(2)] = int(m.group(1))
    tally = lambda pat: sum(v for k, v in cells.items() if pat.search(k))
    return {"cells": sum(cells.values()), "ff": tally(FF_PAT),
            "lut": tally(LUT_PAT), "mul": tally(MUL_PAT)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-families", type=int, default=5,
                    help="fewer than this and the check has not checked much")
    ap.add_argument("--ff-tolerance", type=int, default=32,
                    help="allowed spread in flip-flop count across families")
    args = ap.parse_args()

    # Which yosys produced these numbers, said out loud. The families a build
    # offers and the stat output this script parses both move between versions:
    # under 0.33 every family returns without readable stats and this check
    # reports zero, under 0.62 ten pass and under 0.65 eleven. A result with no
    # tool version attached cannot be compared with the one before it.
    ver = subprocess.run(["yosys", "-V"], capture_output=True, text=True).stdout.strip()
    print(ver.splitlines()[0] if ver else "yosys version unknown")

    fams = available_families()
    if not fams:
        print("FAIL: yosys reported no synth_<family> passes at all")
        return 1

    print(f"yosys offers {len(fams)} candidate families: {' '.join(fams)}\n")
    print(f"{'family':<12}{'cells':>8}{'LUTs':>8}{'FFs':>8}{'mult':>7}  result")

    results, failures, unreadable = {}, [], []
    with tempfile.TemporaryDirectory() as td:
        work = pathlib.Path(td)
        for fam in fams:
            try:
                rc, log = synth(fam, work)
            except subprocess.TimeoutExpired:
                print(f"{fam:<12}{'':>8}{'':>8}{'':>8}{'':>7}  timeout (skipped)")
                continue
            if rc != 0:
                # Not every synth_ pass targets a device we can build for
                # without extra arguments; those are skipped, not failed.
                reason = "needs device arg" if "-family" in log or "no such" in log.lower() else "error"
                print(f"{fam:<12}{'':>8}{'':>8}{'':>8}{'':>7}  {reason} (skipped)")
                continue
            st = parse(log)
            if st["cells"] == 0:
                print(f"{fam:<12}{'':>8}{'':>8}{'':>8}{'':>7}  no stats (skipped)")
                continue
            if st["ff"] == 0:
                # A family that synthesises but whose register cells this script
                # cannot name used to land in `results` -- counting toward "N
                # families checked" -- and then get dropped from the flip-flop
                # comparison by a truthiness filter. It inflated the headline
                # while contributing nothing to the invariant that headline is
                # about. Observed: analogdevices under yosys 0.65 reports 2686
                # cells and zero recognised flip-flops, and the run announced 11
                # families when 10 had agreed.
                print(f"{fam:<12}{st['cells']:>8}{st['lut']:>8}{'0':>8}{st['mul']:>7}"
                      f"  NO FLIP-FLOPS RECOGNISED — not counted, extend FF_PAT")
                unreadable.append(fam)
                continue
            results[fam] = st
            note = ""
            if st["mul"]:
                note = "MULTIPLIER INFERRED"
                failures.append(f"{fam} inferred {st['mul']} multiplier(s); the "
                                f"ternary dot product contains no multiply")
            print(f"{fam:<12}{st['cells']:>8}{st['lut']:>8}{st['ff']:>8}"
                  f"{st['mul']:>7}  {note or 'ok'}")

    print()
    if len(results) < args.min_families:
        print(f"FAIL: only {len(results)} families synthesised; at least "
              f"{args.min_families} are needed for this to mean anything")
        return 1

    # No truthiness filter here any more: a zero never reaches `results`, so
    # every family in it carries a real count and none can be dropped
    # silently from the comparison.
    ffs = {f: r["ff"] for f, r in results.items()}
    if not ffs:
        print("FAIL: no family reported any flip-flops. The cell has "
              "well over a thousand, so the parser is broken, not the design.")
        return 1

    lo, hi = min(ffs.values()), max(ffs.values())
    print(f"sequential state: {lo}..{hi} flip-flops across "
          f"{len(ffs)} families (spread {hi - lo}, tolerance {args.ff_tolerance})")
    if hi - lo > args.ff_tolerance:
        odd = sorted(ffs.items(), key=lambda kv: kv[1])
        failures.append(
            f"flip-flop count disagrees across families by {hi - lo}: "
            f"{', '.join(f'{k}={v}' for k, v in odd)}. Either the design gained "
            f"a vendor dependency or a register was optimised away somewhere.")

    if failures:
        print()
        for f in failures:
            print("  FAIL  " + f)
        return 1

    if unreadable:
        print(f"note: {len(unreadable)} family(ies) synthesised but named no register\n      cell this script knows — {', '.join(unreadable)}. Not counted either way.")
    print(f"OK: {len(results)} families, no multipliers, sequential state agrees")
    return 0


if __name__ == "__main__":
    sys.exit(main())
