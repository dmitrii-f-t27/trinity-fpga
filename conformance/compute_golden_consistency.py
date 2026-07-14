#!/usr/bin/env python3
"""Compute-golden consistency cross-check — RETIRED.

Originally this script cross-checked the independent self-contained integer
references in gf6/gf8/gf12_add_conformance_ax7203.py against gf_ref.py, to
regression-protect against divergence (the way golden_consistency.py protects
the decode host goldens).

Track C of the conformance dedup (2026-07) made gf6/gf8/gf12 import the golden
oracle directly from gf_ref.py, eliminating the duplication. With both sides
being the same code, the cross-check became tautological (gf_add == gf_add)
and was retired.

The bit-exact equivalence of the retired integer references vs gf_ref.py was
confirmed exhaustively before removal:
  - gf6:  4096/4096   (full 64x64 grid)
  - gf8:  65536/65536 (full 256x256 grid)
  - gf12: 27840/27840 (corners + 256-random x 8 corners sample)

gf4/16/20/24 already use gf_ref.py directly (consistent by construction); now
gf6/8/12 do too — the whole family shares one proven oracle.

This stub remains (exits 0) so any CI step / docs referencing it stay valid.
"""
import sys


def main():
    print("COMPUTE GOLDEN CONSISTENCY: retired (gf6/8/12 now import gf_ref.py)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
