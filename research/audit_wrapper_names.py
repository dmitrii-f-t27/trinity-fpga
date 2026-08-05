#!/usr/bin/env python3
"""Does each compute wrapper instantiate the format it is named for?

corona_compute_binary128_add_ax7203.v is headed "BINARY128 ADD on AX7203" and
instantiates

    gf_adder_param #(.EXP_BITS(8), .MANT_BITS(23), .HAS_INF(1))

which is binary32: 8 exponent bits, 23 mantissa bits. binary128 is 15 and 112.

The wrapper filename is what the Tier-E ledger indexes cells by, and what a
conformance host looks up. If the parameters inside disagree with the name
outside, the cell measures a different format from the one it is filed under --
and nothing in the flow compares the two, because the name never reaches the
parameters.

This resolves each wrapper's format name against the oracles and compares
(exp_bits, mant_bits) with what the instantiation actually passes.

Usage:  python3 research/audit_wrapper_names.py [--verbose]

Exits non-zero if any wrapper's parameters contradict its name.
"""
import glob
import importlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")
sys.path.insert(0, CONF)

INST = re.compile(
    r"gf_adder_param\s*#\s*\((?P<p>[^;]*?)\)\s*\w+\s*\(", re.S)
EXP = re.compile(r"\.EXP_BITS\(\s*(\d+)\s*\)")
MANT = re.compile(r"\.MANT_BITS\(\s*(\d+)\s*\)")
NAME = re.compile(r"corona_compute_(?P<fmt>.+?)_(?P<op>add|sub|mul|alu|fma|div|sqrt|quire)_ax7203\.v$")

# The wrapper name uses the catalogue spelling; the oracles sometimes differ.
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


def main():
    verbose = "--verbose" in sys.argv
    mods = oracles()
    rows = []
    for path in sorted(glob.glob(os.path.join(ROOT, "fpga", "**", "*.v"), recursive=True)):
        base = os.path.basename(path)
        m = NAME.search(base)
        if not m:
            continue
        src = open(path, encoding="utf-8", errors="replace").read()
        inst = INST.search(src)
        if not inst:
            continue
        e = EXP.search(inst.group("p"))
        mm = MANT.search(inst.group("p"))
        if not (e and mm):
            continue
        E, M = int(e.group(1)), int(mm.group(1))
        oname, fmt = find(m.group("fmt"), mods)
        if fmt is None:
            rows.append((base, m.group("fmt"), m.group("op"), E, M, None, None, "no oracle"))
            continue
        rows.append((base, m.group("fmt"), m.group("op"), E, M,
                     getattr(fmt, "exp_bits", None), getattr(fmt, "mant_bits", None), oname))

    # Only formats that HAVE a (sign, exponent, mantissa) shape can be compared
    # this way. posit, takum, lns and the integer formats expose no exp_bits, and
    # calling those a mismatch would be comparing a format to a question it does
    # not answer.
    shaped = [r for r in rows if r[5] is not None and r[6] is not None]
    mismatch = [r for r in shaped if (r[3], r[4]) != (r[5], r[6])]
    ok = [r for r in shaped if (r[3], r[4]) == (r[5], r[6])]
    unknown = [r for r in rows if r not in shaped]

    print("compute wrappers with a gf_adder_param instantiation : %d" % len(rows))
    print("with a comparable (sign, exp, mant) shape            : %d" % len(shaped))
    print("parameters MATCH the format in the name              : %d" % len(ok))
    print("parameters CONTRADICT the format in the name         : %d" % len(mismatch))
    print()
    if mismatch:
        print("%-48s %-14s %-5s %-14s %s"
              % ("wrapper", "named format", "op", "instantiated", "the format actually is"))
        for base, fmt, op, E, M, oe, om, oname in sorted(mismatch):
            print("%-48s %-14s %-5s E=%-3d M=%-4d  E=%-3d M=%-4d  (%s)"
                  % (base[:48], fmt, op, E, M, oe, om, oname))
    if verbose and unknown:
        print()
        print("no oracle for the named format: %d" % len(unknown))
        for base, fmt, op, E, M, _a, _b, _c in sorted(unknown):
            print("   %-48s %-14s E=%d M=%d" % (base[:48], fmt, E, M))
    return 1 if mismatch else 0


if __name__ == "__main__":
    sys.exit(main())
