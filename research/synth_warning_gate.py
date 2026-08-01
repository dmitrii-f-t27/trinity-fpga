#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A green synthesis run is not evidence that a design computes anything.

Pass 102 found 2,276 wrappers reading an operand net that nothing drives. This checks
what the toolchain says about them, and what the pipeline did with what it said.

Yosys names the defect in plain words:

    corona_compute_gf16_div_ax7203.v:53: Warning: Identifier `\\fmt_a_a' is
      implicitly declared.
    corona_compute_gf16_div_ax7203.v:54: Warning: Range select [14:9] out of bounds
      on signal `\\fmt_a_a': Setting all 6 result bits to undef.
    corona_compute_gf16_div_ax7203.v:55: Warning: Range select [8:0] out of bounds
      on signal `\\fmt_a_a': Setting all 9 result bits to undef.

Eight such warnings for that file, every operand bit set to undef -- and yosys exits
0. The CI job that built this cell checked the exit code, and GitHub recorded success.
Run 29225131789, job `synth`, conclusion success, on a design whose operands never
arrive.

The tool detected the defect, said so, and the pipeline recorded a pass because
nothing read the warnings. That is the same shape as pass 98's bit-exact hardware
result which bounded the vectors rather than the cell, one layer further down.

This gate reads them. It fails on the diagnostic classes that mean a disconnected
datapath, regardless of exit code.

    python3 research/synth_warning_gate.py [--sample N] [--all] [FILE ...]
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

RTL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "fpga", "openxc7-synth")

# diagnostics that mean the design is not wired the way it reads
FATAL = [
    (re.compile(r"Identifier `\\?(\S+?)' is implicitly declared"),
     "implicitly declared net"),
    (re.compile(r"Range select .*out of bounds on signal `\\?(\S+?)'"),
     "part-select out of bounds -> undef"),
]

OPERAND = re.compile(r"\bfmt_[ab]_[ab]\b")


def yosys_diagnostics(path: str) -> tuple[list[tuple[str, str]], int]:
    """(diagnostics, exit code) from reading one file."""
    try:
        r = subprocess.run(["yosys", "-p", f"read_verilog {os.path.basename(path)}"],
                           cwd=os.path.dirname(path), capture_output=True,
                           text=True, timeout=180)
    except FileNotFoundError:
        print("yosys is not on PATH -- this gate needs it")
        raise SystemExit(2)
    except subprocess.TimeoutExpired:
        return ([("timeout", "yosys did not finish")], -1)
    out = r.stdout + r.stderr
    hits = []
    for line in out.splitlines():
        for rx, why in FATAL:
            m = rx.search(line)
            if m:
                hits.append((m.group(1), why))
    return hits, r.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--sample", type=int, default=25)
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    if args.files:
        targets = args.files
    else:
        flagged = [os.path.join(RTL, f) for f in sorted(os.listdir(RTL))
                   if f.endswith(".v")
                   and OPERAND.search(open(os.path.join(RTL, f), encoding="utf-8",
                                           errors="replace").read())]
        if args.all:
            targets = flagged
        else:
            step = max(1, len(flagged) // args.sample)
            targets = flagged[::step][:args.sample]
        print(f"files statically flagged as reading an undriven operand: "
              f"{len(flagged)}")
        print(f"checking {len(targets)} of them with yosys"
              f"{'' if args.all else ' (a spread sample, and said to be one)'}\n")

    bad = clean = 0
    exit_zero_despite = 0
    for p in targets:
        hits, rc = yosys_diagnostics(p)
        if hits:
            bad += 1
            if rc == 0:
                exit_zero_despite += 1
            nets = sorted({n for n, _ in hits})
            print(f"  {os.path.basename(p):<50} {len(hits):>2} diagnostics  "
                  f"exit {rc}   {', '.join(nets)}")
        else:
            clean += 1

    print(f"\nfiles with a disconnected-datapath diagnostic : {bad}")
    print(f"files clean                                   : {clean}")
    print(f"of the flagged, yosys still exited 0          : {exit_zero_despite}")

    if bad:
        print("""
Every one of these reads an operand that yosys resolves to undef, and every one of
them synthesises with exit code 0. A pipeline that gates on the exit code alone will
record them as passing, which is what happened: the DIV cells' CI ran twice and
reported success before the workflows were removed in an unrelated bulk cleanup.

Gate on the diagnostics, not the exit code.""")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
