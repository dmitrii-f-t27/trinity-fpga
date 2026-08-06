#!/usr/bin/env python3
"""Is a compute wrapper's arithmetic core as wide as the format it carries?

This replaces the claim research/audit_wrapper_names.py made, which was wrong in
its most quotable form. That audit saw

    corona_compute_binary128_add_ax7203.v :
        gf_adder_param #(.EXP_BITS(8), .MANT_BITS(23), .HAS_INF(1))

and reported "instantiates a format other than the one in its name". It does not.
Reading the rest of the file: the wrapper receives 128-bit operands
(`reg [127:0] a_r, b_r`), splits them as binary128 correctly -- sign, 15-bit
exponent, 112-bit mantissa, bias 16383 -- NARROWS each to fp32, adds in fp32, and
widens the fp32 result back to 128 bits by zero-padding.

So the name is truthful about the interface. What it does not say is the
precision. Three things follow, and only the first is a matter of degree:

  1. The mantissa is TRUNCATED, not rounded: `b128_mant_a[111:89]` keeps the top
     23 bits and discards 89. The result carries fp32 precision, about 2**-24
     relative, where binary128 is about 2**-113.
  2. The exponent is truncated to 8 bits from a signed 16-bit intermediate:
     `b128_exp32_a = b128_exp32_s_a[7:0]`. Outside fp32's range that WRAPS
     rather than saturating, so a binary128 value far above fp32's maximum comes
     back as an ordinary finite number instead of +Inf.
  3. Widening back is a zero-pad, so the low 89 mantissa bits of every result
     are zero by construction.

Point 2 is the same class as the decoder wrap pass 238 fixed, in a different
module.

This audit reports, per wrapper, the format width carried at the interface and
the width of the arithmetic core, and models the datapath to count how many of a
structural operand set hit the exponent wrap.

Usage:  python3 research/audit_compute_precision.py [--verbose]
"""
import glob
import importlib
import os
import re
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")
SYNTH = os.path.join(ROOT, "fpga", "openxc7-synth")
sys.path.insert(0, CONF)

CORE = re.compile(r"gf_adder_param\s*#\s*\(\s*\.EXP_BITS\(\s*(\d+)\s*\)\s*,"
                  r"\s*\.MANT_BITS\(\s*(\d+)\s*\)")
OPERAND = re.compile(r"reg \[(\d+):0\] a_r\s*,\s*b_r")
MANT_SLICE = re.compile(r"wire \[22:0\] \w+_mant32_a = \w+_mant_a\[(\d+):(\d+)\];")
EXP_TRUNC = re.compile(r"wire \[7:0\] \w+_exp32_a = \w+_exp32_s_a\[7:0\];")
NAME = re.compile(r"corona_compute_(?P<fmt>.+?)_(?P<op>add|sub|mul|alu|fma)_ax7203\.v$")
ALIAS = {"bf16": "bfloat16", "fp32_e8m23": "binary32", "fp128_e15m112": "binary128"}


def oracles():
    mods = {}
    for path in sorted(glob.glob(os.path.join(CONF, "*_ref.py"))):
        name = os.path.basename(path)[:-3]
        try:
            mods[name] = importlib.import_module(name)
        except Exception:                             # noqa: BLE001
            continue
    return mods


def find(key, mods):
    key = ALIAS.get(key, key)
    for name, mod in mods.items():
        f = getattr(mod, "FORMATS", {}).get(key)
        if f is not None:
            return name, f
    return None, None


def exponent_wrap_count(E, M, bias):
    """How many structural exponents wrap instead of saturating.

    Models exactly `$signed({1'b0, exp}) - bias + 127` truncated to 8 bits: the
    value is representable only when the result already fits 0..255, so anything
    outside that window comes back as some other exponent entirely.
    """
    hit = total = 0
    for e in range(1, (1 << E) - 1):
        total += 1
        v = e - bias + 127
        if not 0 <= v <= 255:
            hit += 1
    return hit, total


def main():
    verbose = "--verbose" in sys.argv
    mods = oracles()
    rows = []
    for path in sorted(glob.glob(os.path.join(SYNTH, "corona_compute_*_ax7203.v"))):
        base = os.path.basename(path)
        m = NAME.search(base)
        if not m:
            continue
        src = open(path, encoding="utf-8", errors="replace").read()
        core = CORE.search(src)
        if not core:
            continue
        cE, cM = int(core.group(1)), int(core.group(2))
        oname, fmt = find(m.group("fmt"), mods)
        E = getattr(fmt, "exp_bits", None)
        M = getattr(fmt, "mant_bits", None)
        if fmt is None or E is None or M is None:
            continue
        if (E, M) == (cE, cM):
            continue                                   # core matches the format
        op = OPERAND.search(src)
        carried = int(op.group(1)) + 1 if op else None
        sl = MANT_SLICE.search(src)
        dropped = (int(sl.group(2))) if sl else None
        wraps = EXP_TRUNC.search(src) is not None
        hit, total = exponent_wrap_count(E, M, getattr(fmt, "bias", 0))
        rows.append((base, m.group("fmt"), m.group("op"), 1 + E + M, carried,
                     cE, cM, dropped, wraps, hit, total))

    full = [r for r in rows if r[4] == r[3]]
    other = [r for r in rows if r[4] != r[3]]
    print("compute wrappers whose core is narrower than the format : %d" % len(rows))
    print("   carrying the format's FULL width at the interface     : %d" % len(full))
    print("   interface width not established from `a_r,b_r`        : %d" % len(other))
    print()
    print("%-44s %-13s %5s %5s %8s %7s %s"
          % ("wrapper", "format", "width", "core", "dropped", "expwrap", "of exps"))
    for base, f, op, w, carried, cE, cM, dropped, wraps, hit, total in rows:
        if carried != w and not verbose:
            continue
        print("%-44s %-13s %5d %5s %8s %7s %d"
              % (base[:44], f, w, "%d+%d" % (cE, cM),
                 "-" if dropped is None else str(dropped),
                 "yes" if wraps else "-", hit if wraps else 0))
    print()
    print("Reading: `width` is what the wrapper carries in and out; `core` is the")
    print("adder it computes with; `dropped` is how many mantissa bits are cut,")
    print("by truncation not rounding; `expwrap` says the 8-bit exponent narrowing")
    print("wraps rather than saturating, and the count is how many of the format's")
    print("own exponents land outside fp32's window.")
    return 1 if rows else 0


if __name__ == "__main__":
    sys.exit(main())
