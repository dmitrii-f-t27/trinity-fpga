#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Do the RTL wrappers actually read the operands they were given?

Pass 101 checked which FIELDS a converting wrapper reads. This checks something more
basic that the field check walked straight past: whether the word it reads them from
is connected to anything.

    wire [15:0] fmt_a = a_reg, fmt_b = b_reg;   // declared, and never used
    wire f_sign_a  = fmt_a_a[15];               // a different identifier
    wire [5:0] f_exp_a  = fmt_a_a[14:9];
    wire [8:0] f_mant_a = fmt_a_a[8:0];

`fmt_a_a` is never declared and never driven. With `default_nettype wire` at the top
of the file it becomes an implicit one-bit net, so every part-select on it is out of
range and the operand never reaches the core. The register holding the actual operand
is `fmt_a`, and nothing reads it.

A second check covers the conversion arithmetic. A wrapper that hands a subnormal to
a binary32 datapath has to normalise it -- find the leading one, shift left by that
much, and subtract the shift from the exponent. A fixed shift with a fixed exponent
cannot do it, because the leading one sits in a different place for every mantissa.
Where the subnormal branch is a constant exponent and a constant shift, the value is
wrong for every subnormal in the format.

Both defects live in wrappers that no conformance script, CI workflow or Tier-E proof
refers to. That was checked rather than assumed -- every Tier-E proof heading in issue
#199 was matched against the affected file list and none of the 75 names one -- but
the check needs the GitHub API, so it is not repeated here. This tool reports the
defects; the closing note records what that comparison found.

    python3 research/audit_rtl_operands.py [--list N]
"""
from __future__ import annotations

import argparse
import collections
import os
import re
import struct
import sys

RTL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "fpga", "openxc7-synth")

OPERAND = re.compile(r"\bfmt_([ab])_([ab])\b")
DRIVEN = "(?:wire|reg)\\s*(?:\\[[^\\]]*\\])?\\s*{n}\\b\\s*(?:=|;|,)"
SUBBR = re.compile(r"fp32_([ab])\s*=\s*\{f_sign_\1,\s*8'd(\d+),\s*"
                   r"f_mant32_norm_\1\}")
NORM = re.compile(r"wire\s*\[22:0\]\s*f_mant32_norm_([ab])\s*=\s*"
                  r"\{1'b0,\s*f_mant_\1,\s*(\d+)'b0\}")


def undriven_operands(text: str) -> list[str]:
    """Operand identifiers that are read but never declared or assigned."""
    bad = []
    for n in sorted({m.group(0) for m in OPERAND.finditer(text)}):
        if re.search(DRIVEN.format(n=n), text) or \
           re.search(rf"^\s*(?:assign\s+)?{n}\s*=", text, re.M):
            continue
        bad.append(n)
    return bad


def fixed_shift_subnormal(text: str):
    """(exponent, shift) where the subnormal branch uses constants for both."""
    b = SUBBR.search(text)
    n = NORM.search(text)
    if b and n and b.group(1) == n.group(1):
        return int(b.group(2)), int(n.group(2))
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", type=int, default=6)
    args = ap.parse_args()

    if not os.path.isdir(RTL):
        print(f"no such directory: {RTL}")
        return 1

    files = sorted(f for f in os.listdir(RTL) if f.endswith(".v"))
    dead, fixed, clean = [], [], 0
    ops = collections.Counter()

    for fn in files:
        text = open(os.path.join(RTL, fn), encoding="utf-8",
                    errors="replace").read()
        bad = undriven_operands(text)
        sub = fixed_shift_subnormal(text)
        if bad:
            dead.append((fn, bad))
            m = re.search(r"_(add|sub|mul|div|sqrt|quire|fma|alu|cmp|decode)_", fn)
            ops[m.group(1) if m else "other"] += 1
        if sub:
            fixed.append((fn, sub))
        if not bad and not sub:
            clean += 1

    print(f"wrappers in {os.path.basename(RTL)} : {len(files)}")
    print(f"  operand net read but never driven : {len(dead)}")
    print(f"  subnormal branch with fixed shift : {len(fixed)}")
    print(f"  neither                           : {clean}\n")

    if dead:
        print("Operand never reaches the core (a sample):")
        for fn, bad in dead[:args.list]:
            print(f"  {fn}   reads {', '.join(bad)}, drives none of them")
        if len(dead) > args.list:
            print(f"  ... and {len(dead) - args.list} more")
        print(f"\n  by operation: "
              + "  ".join(f"{k}={v}" for k, v in sorted(ops.items())))

    if fixed:
        print(f"\nSubnormal branches built from a constant exponent and a constant "
              f"shift: {len(fixed)}.")
        print("  A subnormal's leading one moves with the mantissa, so a single "
              "shift cannot")
        print("  normalise them all. Worked through on one file, using ITS OWN "
              "constants and")
        print("  its own format, rather than mixing numbers from different cells:")
        pick = next((x for x in fixed if "gf16_div" in x[0]), fixed[0])
        fn, (e, sh) = pick
        fmt = re.match(r"corona_compute_(\w+?)_(?:add|sub|mul|div|sqrt|quire|fma|"
                       r"alu|cmp)_", fn)
        print(f"    {fn}  (exponent {e}, shift {sh})")
        if fmt and fmt.group(1) == "gf16":
            mant_bits, bias = 9, 31            # gf16, from the catalog
            for mant in (1, 2 ** mant_bits - 1):
                word = (e << 23) | ((mant << sh) & 0x7FFFFF)
                got = struct.unpack(">f", struct.pack(">I", word))[0]
                true = mant * 2.0 ** (1 - bias - mant_bits)
                print(f"      mant {mant:<4} true {true:.6e}   built {got:.6e}"
                      f"   ratio {got / true:.2e}")
            print("      every subnormal in the format converts to the wrong value")
        else:
            print("      (no gf16 converting wrapper found to work through)")

    print("""
Neither defect can be reached by anything that runs. The cells carrying them have no
conformance script, no CI workflow naming them, and no Tier-E proof -- checked, not
assumed. The wrappers behind the 75 published proofs do not convert at all: they hand
the operand to a parametric core at its native width, so there is no conversion in
them to get wrong.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
