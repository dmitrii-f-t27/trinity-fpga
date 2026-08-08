#!/usr/bin/env python3
"""Does every synthesis wrapper still parse, and does each set HAS_INF?

Pass 237 found nine wrappers in fpga/openxc7-synth that iverilog rejects outright:

    gf_decode_param #(.N(24), .E(9, .HAS_INF(0)), .M(14), .BIAS(255), .OUT_REG(1))
                              ^^^^^^^^^^^^^^^^^

`.HAS_INF(0)` had been spliced INSIDE the `.E(...)` expression. It came from
PR #396, whose whole purpose was to give gf_decode_param the HAS_INF parameter --
the parameter arrived and the nine call sites that were meant to use it stopped
compiling. Nothing noticed, because nothing checked that the wrappers parse.

A file that does not parse cannot be synthesised, so any bitstream for those
widths predates the edit.

The second check is semantic. gf_decode_param defaults HAS_INF to 1, deliberately,
so that adding the parameter changed nothing on its own -- which means every
wrapper for a format WITHOUT Inf has to set it to 0 explicitly, and silence is
wrong rather than neutral. Only gf16 (and gf_lns_hybrid, which uses gf16's exact
layout) should leave it at the default.

Usage:  python3 research/audit_rtl_parses.py

Exits non-zero on a parse failure or a missing HAS_INF.
"""
import glob
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SYNTH = os.path.join(ROOT, "fpga", "openxc7-synth")
CORE = os.path.join(SYNTH, "gf_decode_param.v")

# The only layouts that reserve exp=all-ones. gf_lns_hybrid instantiates gf16's
# exact parameters (E=6, M=9, BIAS=31), so it inherits gf16's convention.
HAS_INF_EXPECTED_1 = {"gf16", "gf_lns_hybrid"}

INST = re.compile(r"gf_decode_param\s*#\s*\((?P<params>[^;]*?)\)\s*\w+\s*\(", re.S)
SYNTAX = re.compile(r"syntax error", re.I)


def parses(path):
    """iverilog -t null. Missing Xilinx primitives are expected, syntax is not."""
    out = subprocess.run(["iverilog", "-t", "null", path, CORE],
                         capture_output=True, text=True)
    text = out.stdout + out.stderr
    return (not SYNTAX.search(text)), text


def main():
    if shutil.which("iverilog") is None:
        print("iverilog not on PATH -- cannot check. Install it or run this in CI.")
        return 2
    files = sorted(glob.glob(os.path.join(SYNTH, "*.v")))
    bad_parse, bad_hasinf, checked = [], [], 0
    for path in files:
        name = os.path.basename(path)
        if name == "gf_decode_param.v":
            continue
        ok, text = parses(path)
        checked += 1
        if not ok:
            first = next((ln for ln in text.splitlines() if SYNTAX.search(ln)), "")
            bad_parse.append((name, first.strip()))
            continue
        src = open(path, encoding="utf-8", errors="replace").read()
        for m in INST.finditer(src):
            params = m.group("params")
            stem = name[len("corona_decode_"):-len("_ax7203.v")] \
                if name.startswith("corona_decode_") else name
            has = ".HAS_INF" in params
            if stem in HAS_INF_EXPECTED_1:
                if has and not re.search(r"\.HAS_INF\(\s*1\s*\)", params):
                    bad_hasinf.append((name, "sets HAS_INF to 0 but this layout HAS Inf"))
            elif not has:
                bad_hasinf.append((name, "does not set HAS_INF -- defaults to 1, "
                                         "so exp=all-ones becomes Inf/NaN"))

    print("wrappers checked          : %d" % checked)
    print("fail to PARSE             : %d" % len(bad_parse))
    for n, why in bad_parse:
        print("   %-46s %s" % (n, why))
    print("wrong or missing HAS_INF  : %d" % len(bad_hasinf))
    for n, why in bad_hasinf:
        print("   %-46s %s" % (n, why))
    return 1 if (bad_parse or bad_hasinf) else 0


if __name__ == "__main__":
    sys.exit(main())
