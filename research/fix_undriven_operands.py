#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Connect the operand nets that 2,276 wrappers read but nothing drives.

Pass 102 found the defect, pass 103 watched yosys name it and the CI pipeline record
a pass anyway. The repair itself is small: the wrappers declare

    wire [15:0] fmt_a = a_reg, fmt_b = b_reg;

and then read `fmt_a_a` and `fmt_b_b`, which are never declared. Each suffix is
doubled. The three-operand FMA cells add `fmt_c = c_reg` and read `fmt_c_c`.

Small does not mean safe to apply blindly across 2,276 files, so every rewrite is
guarded:

  the target identifier must already be declared in that file, with a width, before
  anything is renamed to it -- otherwise the file is skipped and listed

  the doubled name must not itself be declared anywhere, or renaming it would merge
  two real nets

  nothing else in the file is touched

Verify with research/synth_warning_gate.py, which reads what yosys says rather than
what it returns.

    python3 research/fix_undriven_operands.py [--apply] [--limit N]
"""
from __future__ import annotations

import argparse
import os
import re
import sys

RTL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "fpga", "openxc7-synth")

DOUBLED = re.compile(r"\bfmt_([abc])_\1\b")


def declared(text: str, name: str) -> bool:
    """Is `name` declared as a net with a width in this file?"""
    return re.search(rf"(?:wire|reg)\s*\[[^\]]*\]\s*(?:\w+\s*=\s*\w+\s*,\s*)*"
                     rf"{name}\s*=", text) is not None


def plan(text: str):
    """(renames, blockers) for one file."""
    names = sorted({m.group(0) for m in DOUBLED.finditer(text)})
    renames, blockers = [], []
    for bad in names:
        good = bad[:-2]                      # fmt_a_a -> fmt_a
        if not declared(text, good):
            blockers.append(f"{good} is not declared")
            continue
        if declared(text, bad):
            blockers.append(f"{bad} is itself declared -- renaming would merge nets")
            continue
        renames.append((bad, good))
    return renames, blockers


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write the files; without this it is a dry run")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    files = sorted(f for f in os.listdir(RTL) if f.endswith(".v"))
    touched = skipped = 0
    total_renames = 0
    skip_reasons = []

    for fn in files:
        p = os.path.join(RTL, fn)
        text = open(p, encoding="utf-8", errors="replace").read()
        if not DOUBLED.search(text):
            continue
        renames, blockers = plan(text)
        if blockers:
            skipped += 1
            skip_reasons.append((fn, blockers))
            continue
        if not renames:
            continue
        new = text
        for bad, good in renames:
            new = re.sub(rf"\b{bad}\b", good, new)
        if args.apply:
            open(p, "w", encoding="utf-8").write(new)
        touched += 1
        total_renames += len(renames)
        if args.limit and touched >= args.limit:
            break

    mode = "rewritten" if args.apply else "would be rewritten (dry run)"
    print(f"files {mode:<34}: {touched}")
    print(f"distinct nets reconnected           : {total_renames}")
    print(f"files skipped for safety            : {skipped}")
    for fn, why in skip_reasons[:10]:
        print(f"  {fn}\n      {'; '.join(why)}")
    if skipped > 10:
        print(f"  ... and {skipped - 10} more")

    if not args.apply:
        print("\nDry run. Re-run with --apply to write, then verify with"
              "\n  python3 research/synth_warning_gate.py --sample 20")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
