#!/usr/bin/env python3
"""Add the div, quire and sqrt cores to build-matrix.yml's source list.

.github/workflows/build-matrix.yml builds any compute target from exactly three
files:

    READS="gf_adder_param.v gf_mul_param.v ${DESIGN}.v"

That is enough for add, sub, mul, alu, fma and cmp. It is not enough for div,
quire or sqrt, whose wrappers instantiate gf_div_param, gf_quire_param and
gf_sqrt_param -- none of which the list supplies. Dispatching any of those
targets fails at elaboration with "Module ... is not part of the design".

36 of the 3,203 compute wrappers are affected: 16 need gf_div_param, 10 need
gf_quire_param, 10 need gf_sqrt_param.

Adding the three files is safe and follows the pattern already there -- the list
already supplies gf_mul_param to an ADD target that does not use it. Verified by
synthesising bf16_div, gf16_quire and bf16_sqrt with the extended list under the
workflow's own flags: all three build.

Run:  python3 research/apply_build_matrix_reads.py [--write]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WF = os.path.join(ROOT, ".github", "workflows", "build-matrix.yml")

# Pass 284 measured the full sweep and found 37 targets in this class, not 36.
# The three cores below fix 36 of them. The 37th,
# corona_compute_gf16_plus_mac_ax7203, instantiates gf16_plus_mac -- which exists
# as fpga/openxc7-synth/gf16_plus_mac.v and was simply never listed. Adding it
# makes that target build too, verified under the workflow's own flags.
OLD = ('READS="gf_adder_param.v gf_mul_param.v gf_div_param.v '
       'gf_quire_param.v gf_sqrt_param.v ${DESIGN}.v"')
NEW = ('READS="gf_adder_param.v gf_mul_param.v gf_div_param.v '
       'gf_quire_param.v gf_sqrt_param.v gf16_plus_mac.v ${DESIGN}.v"')


def main():
    write = "--write" in sys.argv
    if not os.path.exists(WF):
        print("not found: %s" % WF)
        return 2
    src = open(WF, encoding="utf-8").read()
    if NEW in src:
        print("already applied")
        return 0
    if OLD not in src:
        print("the READS line does not match what this script expects:")
        print("   %s" % OLD)
        print("Refusing to guess. Inspect the workflow by hand.")
        return 1
    out = src.replace(OLD, NEW)
    print("- %s" % OLD)
    print("+ %s" % NEW)
    if write:
        with open(WF, "w", encoding="utf-8") as fh:
            fh.write(out)
        print("written")
    else:
        print("dry run -- pass --write to apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
