#!/usr/bin/env python3
"""Which mantissa narrowings truncate, and which round?

The last of the repeating classes to get a check. The zero-sign class was found
five times before pass 242 gave it one; this one has been counted twice --
172 sites in pass 235's structural audit, and again in pass 240's reading of the
compute wrappers -- and has never had a guard.

A narrowing looks like this:

    wire [22:0] X_mant32_a = X_mant_a[111:89];

23 bits kept, 89 discarded, no rounding term anywhere. Round-to-nearest-even
needs a guard bit, a sticky OR below it, and an increment that can carry:

    guard  = mant[88]
    sticky = |mant[87:0]

so a narrowing that rounds has those signals near it and a truncating one does
not. That is what this looks for.

It reports rather than fails. research/witness_rounding.py measures what the
difference is worth -- 160 wrong of 448 truncating, 0 rounding, at +73 LUTs per
port -- and the decision of whether to take it belongs to whoever weighs those,
not to a lint.

Usage:  python3 research/audit_truncation.py [--verbose]
"""
import collections
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SYNTH = os.path.join(ROOT, "fpga", "openxc7-synth")

SLICE = re.compile(r"wire\s*\[22:0\]\s*(\w+)\s*=\s*(\w+)\[(\d+):(\d+)\]\s*;")
ROUNDING = re.compile(r"\bsticky\b|\bguard\b|\bround_up\b|\brnd\b|\|\s*\w+\[\d+:0\]")


def main():
    verbose = "--verbose" in sys.argv
    trunc, rounds, exact = [], [], 0
    for path in sorted(glob.glob(os.path.join(SYNTH, "*.v"))):
        src = open(path, encoding="utf-8", errors="replace").read()
        base = os.path.basename(path)
        for m in SLICE.finditer(src):
            dst, srcw, hi, lo = m.group(1), m.group(2), int(m.group(3)), int(m.group(4))
            dropped = lo
            if hi - lo != 22:
                continue                      # not a 23-bit take
            if dropped == 0:
                exact += 1                    # nothing discarded
                continue
            # look for rounding signals in the 400 characters around the slice
            near = src[max(0, m.start() - 200):m.end() + 400]
            (rounds if ROUNDING.search(near) else trunc).append((base, dst, dropped))

    by_drop = collections.Counter(d for _b, _n, d in trunc)
    print("23-bit mantissa narrowings in fpga/openxc7-synth")
    print("  discard nothing (exact)      : %d" % exact)
    print("  discard bits WITH rounding   : %d" % len(rounds))
    print("  discard bits by TRUNCATION   : %d" % len(trunc))
    print()
    if trunc:
        print("  bits dropped, by how many sites:")
        for d, n in sorted(by_drop.items(), key=lambda kv: -kv[0]):
            print("     %4d bits discarded : %d sites" % (d, n))
        if verbose:
            print()
            for base, dst, d in sorted(trunc):
                print("     %-46s %-24s drops %d" % (base[:46], dst, d))
    print()
    print("Reported, not failed. research/witness_rounding.py measures the trade:")
    print("160 of 448 structural cases wrong truncating, 0 rounding, +73 LUTs a port.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
