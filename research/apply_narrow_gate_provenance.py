#!/usr/bin/env python3
"""Correct the evidence sentence in narrow-register-gate.yml's header.

The header cites pass 146 running yosys over trinity_v1_morse.v and seeing zero
warnings. yosys has never been able to read that file -- line 113 is a
SystemVerilog assignment pattern the frontend rejects as OP_CAST, in plain mode
and under -sv, and the pre-pass-146 revision fails at the same construct. "Zero
warnings" is what a refused read produces.

The claim the sentence supports is nonetheless TRUE, and now has real evidence:
research/witness_narrow_register_silence.py exercises five narrowings on modules
yosys can actually read and gets silence on all five.

So this does not weaken the gate, and does not touch what it runs. It replaces a
citation of an experiment that could not have happened with one that did.

Run:  python3 research/apply_narrow_gate_provenance.py [--write]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WF = os.path.join(ROOT, ".github", "workflows", "narrow-register-gate.yml")

OLD = """# A register narrower than the constant it is compared against, or than the slice
# assigned into it, is legal Verilog and silent in yosys -- pass 146 confirmed that by
# running yosys over trinity_v1_morse.v, which compared a 25-bit register against
# 1,500,000,000 and produced zero warnings. Fifteen real defects were found this way,"""

NEW = """# A register narrower than the constant it is compared against, or than the slice
# assigned into it, is legal Verilog and silent in yosys. Established by
# research/witness_narrow_register_silence.py, which exercises five narrowings --
# comparison, assignment, slice, port connection, dead control branch -- on minimal
# modules and gets no width warning on any of them.
#
# This header used to cite pass 146 running yosys over trinity_v1_morse.v and seeing
# zero warnings. yosys has never been able to read that file: line 113 is a
# SystemVerilog assignment pattern rejected as OP_CAST, in plain mode and under -sv,
# and the revision that preceded pass 146's own edit fails at the same construct.
# Zero warnings is what a refused read produces. The claim was right; the evidence
# for it was a failure misread as a silence. Corrected in pass 278.
#
# Fifteen real defects were found this way,"""


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
        print("the header does not match what this script expects. Refusing to guess.")
        return 1
    out = src.replace(OLD, NEW)
    print("replacing the provenance sentence (%d -> %d chars)" % (len(src), len(out)))
    if write:
        with open(WF, "w", encoding="utf-8") as fh:
            fh.write(out)
        print("written")
    else:
        print("dry run -- pass --write to apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
