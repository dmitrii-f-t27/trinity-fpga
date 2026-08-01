#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Do the RTL wrappers read their input with the layout their name claims?

Passes 99 and 100 found a format's constants written for the wrong layout twice in
one host file: once in the conformance vectors, once in the self-test's NaN mask.
Both were on the host. This asks the same of the layer underneath, which had never
been checked and which is the one that decides what the silicon does.

Two things are checked, and the second only became visible after the first was fixed:

  layout   a wrapper that converts its operands to binary32 before handing them to a
           parametric core must still DECODE the incoming word with its own format's
           field widths and bias

  specials a wrapper must not invent Inf and NaN for a format that has neither. Most
           GoldenFloat rungs have no Inf -- gf_ref gives it to gf16 alone -- so for
           them the all-ones exponent is an ordinary finite band, and treating it as
           a sentinel misreads the largest values in the format

The check is narrow on purpose. A first attempt compared the parameters each wrapper
passes to its core against the named format and reported 18 mismatches; every one was
correct code, because div, sqrt and quire run a binary32 datapath by design and say
so in the surrounding lines. Only the input decode can be wrong about the source
format, so only the input decode is read.

    python3 research/audit_rtl_layout.py
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "conformance"))

from gf_ref import FORMATS                                # noqa: E402

RTL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "fpga", "openxc7-synth")

CELL = re.compile(r"corona_compute_(gf\d+)_\w+_ax7203\.v$")
EXP = re.compile(r"wire\s*\[(\d+):(\d+)\]\s*f_exp_a\s*=\s*\w+\[(\d+):(\d+)\]")
MANT = re.compile(r"wire\s*\[(\d+):(\d+)\]\s*f_mant_a\s*=\s*\w+\[(\d+):(\d+)\]")
BIAS = re.compile(r"f_de_a\s*=.*?-\s*\d+'sd(\d+)\s*\+\s*\d+'sd127")
SENTINEL = re.compile(r"wire\s+f_(inf|nan)_a\s*=\s*\(f_exp_a\s*==\s*(\d+)\)")


def main() -> int:
    if not os.path.isdir(RTL):
        print(f"no such directory: {RTL}")
        return 1

    checked = layout_bad = spec_bad = 0
    skipped = 0
    for fn in sorted(os.listdir(RTL)):
        m = CELL.match(fn)
        if not m:
            continue
        fmt = FORMATS.get(m.group(1))
        if fmt is None:
            skipped += 1
            continue
        text = open(os.path.join(RTL, fn), encoding="utf-8",
                    errors="replace").read()
        e, mm, b = EXP.search(text), MANT.search(text), BIAS.search(text)
        if not (e and mm and b):
            continue                      # not a converting wrapper; nothing to read
        checked += 1

        ebits = int(e.group(3)) - int(e.group(4)) + 1
        mbits = int(mm.group(3)) - int(mm.group(4)) + 1
        bias = int(b.group(1))
        if (ebits, mbits, bias) != (fmt.exp_bits, fmt.mant_bits, fmt.bias):
            layout_bad += 1
            print(f"  LAYOUT   {fn}")
            print(f"           decodes as 1+{ebits}E+{mbits}M bias {bias}, "
                  f"but {fmt.name} is 1+{fmt.exp_bits}E+{fmt.mant_bits}M "
                  f"bias {fmt.bias}")

        if not fmt.has_inf:
            phantom = SENTINEL.findall(text)
            if phantom:
                spec_bad += 1
                band = 2 * (1 << fmt.mant_bits)
                width = 1 + fmt.exp_bits + fmt.mant_bits
                print(f"  SPECIAL  {fn}")
                print(f"           declares Inf/NaN, but {fmt.name} has neither; "
                      f"the all-ones exponent is finite")
                print(f"           {band} of {1 << width} codes "
                      f"({100 * band / (1 << width):.1f}%) would be misread")

    print(f"\nconverting wrappers checked : {checked}")
    print(f"  wrong input layout        : {layout_bad}")
    print(f"  phantom Inf/NaN           : {spec_bad}")
    if skipped:
        print(f"  wrappers whose format is unknown to gf_ref (not checked): {skipped}")
    if not (layout_bad or spec_bad):
        print("""
Every converting wrapper reads its input with its own format's fields and bias, and
none invents a sentinel its format does not have.

Worth remembering what this layer is: none of these cells has a conformance script,
a CI workflow that names it, or a Tier-E proof. No published claim rests on them --
which is also why nothing ever contradicted them.""")
    return 1 if (layout_bad or spec_bad) else 0


if __name__ == "__main__":
    raise SystemExit(main())
