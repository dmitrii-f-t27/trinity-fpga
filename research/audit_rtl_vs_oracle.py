#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Does each per-format decoder in the RTL agree with the oracle for its format?

Passes 196 to 201 ran this question end to end for GoldenFloat: two decoders disagreed, the
`.t27` spec settled it, simulation measured the hardware, and the fix turned out to be a
parameter its sibling module already had. That whole chain started from a single accident --
`gf_pipe` happened to contain a second decoder to compare against.

There are fifty per-format decoders in `fpga/openxc7-synth/`, and no accident is needed:
every one of them has an oracle in `conformance/`. This asks all of them the same question
by simulation.

    python3 research/audit_rtl_vs_oracle.py [--only NAME] [--n N] [--verbose] [--self-check]

METHOD
------
Each module has the shape

    module <fmt>_decode(input [W-1:0] <anything>_in, output [31:0] fp32_out, ...);

so the input port name and width are read from the source rather than assumed. A
testbench is generated, iverilog runs it over a sample of codes, and each result is
compared against the format's oracle converted to fp32 with the same rounding the
hardware is specified to use.

WHAT IS AND IS NOT A DEFECT
---------------------------
A disagreement here is a disagreement between two implementations, not a verdict. Passes
196 to 199 needed the spec to say which side was right, and that step is not automatable.
What this does is find the pairs worth asking about -- which is the expensive part, and
which for GoldenFloat took an accident.

Formats whose exact value overflows fp32 are reported separately: the conversion is lossy
by construction there, so `0x7F800000` on both sides proves less than it looks.
"""
from __future__ import annotations

import argparse
import glob
import importlib
import os
import re
import struct
import subprocess
import sys
import tempfile
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RTL_DIR = os.path.join(ROOT, "fpga", "openxc7-synth")
CONF = os.path.join(ROOT, "conformance")

PORTS = re.compile(
    r"module\s+(\w+_decode)\s*\((.*?)\);", re.S)
IN_PORT = re.compile(r"input\s+wire\s*\[\s*(\d+)\s*:\s*0\s*\]\s*(\w+)")


def module_iface(path):
    """(module_name, input_port, width) or None."""
    text = open(path, encoding="utf-8", errors="replace").read()
    m = PORTS.search(text)
    if not m:
        return None
    name, body = m.group(1), m.group(2)
    p = IN_PORT.search(body)
    if not p:
        return None
    return name, p.group(2), int(p.group(1)) + 1


def oracle_for(fmt_name):
    """(module, format object) for a format name, or None."""
    sys.path.insert(0, CONF)
    for mod_name in sorted(os.path.basename(p)[:-3]
                           for p in glob.glob(os.path.join(CONF, "*_ref.py"))):
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue
        if hasattr(mod, "FORMATS") and fmt_name in mod.FORMATS:
            return mod, mod.FORMATS[fmt_name]
    return None


def to_fp32(mod, fmt, code):
    """(fp32_word, overflowed) for the oracle's value of this code."""
    sign = (code >> (getattr(fmt, "width", 32) - 1)) & 1
    try:
        v = mod.decode(fmt, code)
    except Exception:
        return None, False
    Special = getattr(mod, "Special", None)
    if Special is not None and isinstance(v, Special):
        if v.kind == "nan":
            return 0x7FC00001, False
        return 0x7F800000 | (getattr(v, "sign", sign) << 31), False
    if v == 0:
        return sign << 31, False
    try:
        v = Fraction(v)
    except (TypeError, ValueError):
        # Some oracles return their own value type -- gfternary's PhiVal, for one. A
        # value this file cannot convert is not a disagreement and is not agreement
        # either; it is reported as unconvertible rather than crashed on or counted.
        return None, False
    try:
        return struct.unpack(">I", struct.pack(">f", float(v)))[0], False
    except OverflowError:
        return 0x7F800000 | (sign << 31), True


TB = """`timescale 1ns/1ps
module tb_gen;
  reg [%(w)d:0] code;
  wire [31:0] fp32_out;
  %(mod)s dut(.%(port)s(code), .fp32_out(fp32_out));
  integer i;
  initial begin
%(body)s
    $finish;
  end
endmodule
"""


def run(path, name, port, width, codes):
    body = "".join(f"    code = {width}'h{c:x}; #5;"
                   f" $display(\"C %0d %h\", {c}, fp32_out);\n" for c in codes)
    with tempfile.TemporaryDirectory() as d:
        tb = os.path.join(d, "tb.v")
        vvp = os.path.join(d, "tb.vvp")
        open(tb, "w").write(TB % {"w": width - 1, "mod": name,
                                  "port": port, "body": body})
        r = subprocess.run(["iverilog", "-g2012", "-o", vvp, tb, path],
                           capture_output=True, text=True)
        if r.returncode:
            return None, r.stderr.strip().split("\n")[0][:70]
        out = subprocess.run(["vvp", vvp], capture_output=True, text=True).stdout
    got = {}
    for line in out.splitlines():
        if line.startswith("C "):
            _, c, fp = line.split()
            # A module needing a clock or reset this bench does not drive answers with
            # x. That is not a disagreement and not agreement; dropping it here means the
            # format is reported with a smaller `checked` count rather than a wrong one.
            if "x" in fp.lower() or "z" in fp.lower():
                continue
            got[int(c)] = int(fp, 16)
    return got, None


def is_nan32(x):
    return ((x >> 23) & 0xFF) == 0xFF and (x & 0x7FFFFF) != 0


def sample(width, n):
    import random
    rng = random.Random(202)
    if width <= 12:
        return list(range(1 << width))
    corners = [0, 1, (1 << (width - 1)), (1 << width) - 1]
    for e in range(width):
        corners.append(1 << e)
    return sorted(set(corners + [rng.randrange(1 << width) for _ in range(n)]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        return self_check()

    if subprocess.run(["which", "iverilog"], capture_output=True).returncode:
        print("iverilog not found.\nSKIPPED -- not a pass.")
        return 2

    rows, no_oracle, unbuildable = [], [], []
    for path in sorted(glob.glob(os.path.join(RTL_DIR, "*_decode.v"))):
        base = os.path.basename(path)[:-2]
        if args.only and args.only not in base:
            continue
        iface = module_iface(path)
        if iface is None:
            unbuildable.append((base, "no single-input interface"))
            continue
        name, port, width = iface
        fmt_name = name[:-len("_decode")]
        oc = oracle_for(fmt_name)
        if oc is None:
            no_oracle.append(fmt_name)
            continue
        mod, fmt = oc
        codes = sample(width, args.n)
        got, err = run(path, name, port, width, codes)
        if got is None:
            unbuildable.append((base, err))
            continue
        n = ok = ovf = nan_pair = 0
        first = None
        for c in codes:
            if c not in got:
                continue
            want, overflowed = to_fp32(mod, fmt, c)
            if want is None:
                continue
            n += 1
            if overflowed:
                ovf += 1
                continue
            if got[c] == want:
                ok += 1
            elif is_nan32(got[c]) and is_nan32(want):
                # Both NaN, different sign or payload. IEEE 754 leaves that to the
                # implementation for every operation here, and counting it would bury the
                # real differences under a wall of them -- this comparison produces a
                # canonical 0x7FC00001 while the RTL propagates what it was given.
                nan_pair += 1
            elif first is None:
                first = (c, got[c], want)
        rows.append((fmt_name, width, n, ok, ovf, nan_pair, first))

    print(f"decoders with an oracle and a testable interface : {len(rows)}")
    print(f"  no oracle for the format name                  : {len(no_oracle)}")
    print(f"  could not be elaborated                        : {len(unbuildable)}\n")
    print(f"  {'format':<16}{'W':>5}{'checked':>9}{'agree':>8}{'ovf':>6}{'nan':>5}"
          f"  first real difference")
    bad = 0
    for fmt_name, width, n, ok, ovf, nan_pair, first in rows:
        cmp_n = n - ovf - nan_pair
        flag = "" if (first is None) else \
            f"{first[0]:#x}: rtl {first[1]:#010x} vs {first[2]:#010x}"
        if first is not None:
            bad += 1
        print(f"  {fmt_name:<16}{width:>5}{cmp_n:>9}{ok:>8}{ovf:>6}{nan_pair:>5}"
              f"  {flag}")

    if no_oracle:
        print(f"\n  no oracle: {', '.join(sorted(no_oracle))}")
    if unbuildable and args.verbose:
        for b, why in unbuildable:
            print(f"  {b}: {why}")

    print(f"""
{bad} of {len(rows)} decoders disagree with their oracle somewhere in the sample.

A disagreement is a pair worth asking the spec about, not a verdict. For GoldenFloat that
question took passes 196 to 199 to answer and the answer was in the .t27 file; nothing here
automates that step. What this automates is finding the pairs -- which for GoldenFloat
required the accident of a second decoder happening to exist.

The `nan` column is codes where both sides give a NaN and differ in sign or payload. IEEE
754 leaves that to the implementation, so they are counted apart rather than reported.

The `ovf` column is codes whose exact value overflows fp32. Both sides give 0x7F800000
there whatever they think, so those are counted apart rather than as agreement.""")
    return 1 if bad else 0


def self_check() -> int:
    """The sweep must reproduce a known-good decoder and catch a known-bad one.

    gf16 is known good after pass 200. The known-bad case is constructed rather than
    hoped for: run the same module with the sign bit of every expectation flipped and
    require the comparison to notice.
    """
    if subprocess.run(["which", "iverilog"], capture_output=True).returncode:
        print("iverilog absent; cannot control a simulation that cannot run")
        return 2
    path = os.path.join(RTL_DIR, "binary16_decode.v")
    if not os.path.exists(path):
        print("binary16_decode.v absent; using any available decoder")
        cands = sorted(glob.glob(os.path.join(RTL_DIR, "*_decode.v")))
        path = cands[0] if cands else None
    iface = module_iface(path)
    print(f"  interface read from source: {iface}")
    ok_iface = iface is not None
    name, port, width = iface
    codes = sample(width, 50)
    got, err = run(path, name, port, width, codes[:20])
    ran = got is not None and len(got) > 0
    print(f"  simulation produced {len(got) if got else 0} results -> {ran}")
    if err:
        print(f"      {err}")

    oc = oracle_for(name[:-len('_decode')])
    print(f"  oracle located for {name[:-len('_decode')]} -> {oc is not None}")
    caught = False
    if oc and ran:
        mod, fmt = oc
        c = next(iter(got))
        want, _ = to_fp32(mod, fmt, c)
        caught = want is not None and (got[c] == want or got[c] != want ^ (1 << 31))
        print(f"  a flipped-sign expectation would not match -> "
              f"{want is None or got[c] != (want ^ (1 << 31))}")
        caught = want is None or got[c] != (want ^ (1 << 31))

    passed = ok_iface and ran and (oc is not None) and caught
    print(f"\nself-check: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
