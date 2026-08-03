#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Do a pack's results ever use the whole width of the format?

One cheap question, asked of every vector file: OR every stored result together, and OR
every operand together, and see which bits never appear. Operands come from a generator
and are expected to cover the word. Results come from arithmetic, and arithmetic on
full-width operands lands on full-width answers.

A run of bits that is never set in any result, while the operands set every bit, says the
answers were produced in something narrower than the format. It does not say what -- and
this file is careful not to guess.

    python3 research/audit_result_bit_coverage.py [--verbose] [--self-check]

WHAT IT FOUND
-------------
    bf16, fp16_e6m9, fp24_7m16, fp32_e8m23, gf8, gf16      0 dead bits
    gf32            (div, quire, sqrt)                     2, run starting at bit 23
    binary64        (div, quire, sqrt)                    29, run starting at bit 23
    fp128_e15m112   (add, div, mul, quire, sqrt)          89, run starting at bit 23

29 and 89 are not arbitrary. They are 52 - 23 and 112 - 23: the difference between the
format's significand and binary32's. Every result in those packs is missing precisely the
bits a binary32 significand cannot carry, and the operands beside them set every bit. The
run begins at bit 23 in all three formats, which is the part that makes it a signature
rather than a coincidence.

Two things are deliberately NOT flagged. Every `_sqrt` pack has its sign bit dead, which
is the square root of a non-negative argument behaving correctly. And gf4_sqrt has one
dead bit in a 4-bit format sampled 64 times, which is a small-sample artefact rather than
a shape.

That is where the identification stops. Reconstructing the arithmetic did not work: the
binary64 packs are not binary64 division (46 of 384) and not binary32 division widened
to binary64 (0 of 384) either. The structure is a strong and specific signal; the cause
is somebody else's generator, and a guess dressed as a diagnosis would be worse than the
open question.

Related: pass 189 established these same packs have no oracle in the corpus for div, sqrt
or quire, so nothing could have re-derived them and nothing did. See
research/audit_pack_vs_oracle.py.
"""
from __future__ import annotations

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VEC = os.path.join(ROOT, "conformance", "vectors")


def num(x):
    if isinstance(x, str):
        return int(x, 16)
    if isinstance(x, int):
        return x
    return None


def scan(path):
    """(width, vectors, dead_result_bits, dead_operand_bits) or None."""
    doc = json.load(open(path, encoding="utf-8"))
    vectors = doc.get("vectors") or []
    if not vectors:
        return None
    or_r = or_ab = 0
    n = 0
    for v in vectors:
        r = num(v.get("expected", v.get("result")))
        a, b = num(v.get("a")), num(v.get("b"))
        if r is None or a is None or b is None:
            continue
        or_r |= r
        or_ab |= a | b
        n += 1
    if not n:
        return None
    width = max(or_r.bit_length(), or_ab.bit_length())
    dead = [i for i in range(width) if not (or_r >> i) & 1]
    # A square root of a non-negative argument never sets the sign bit. That is the
    # operation behaving correctly, and counting it would have this check crying wolf on
    # six packs whose only dead bit is the sign.
    if os.path.basename(path).endswith("_sqrt.json") and dead and dead[-1] == width - 1:
        dead = dead[:-1]
    dead_ab = sum(1 for i in range(width) if not (or_ab >> i) & 1)
    return width, n, len(dead), dead_ab, (dead[0] if dead else None)


def main() -> int:
    verbose = "--verbose" in sys.argv
    rows = []
    for path in sorted(glob.glob(os.path.join(VEC, "*.json"))):
        got = scan(path)
        if got is None:
            continue
        width, n, dead_r, dead_ab, first = got
        rows.append((os.path.basename(path)[:-5], width, n, dead_r, dead_ab, first))

    # A pack is suspect when its results miss bits its own operands reach. Operands
    # missing bits is a different question -- that is coverage, and pass 188 measured it.
    suspect = [r for r in rows if r[3] > r[4]]

    print(f"vector files scanned                 : {len(rows)}")
    print(f"  results narrower than their operands : {len(suspect)}\n")

    if suspect:
        print(f"  {'pack':<26}{'width':>7}{'vectors':>9}"
              f"{'dead result bits':>18}{'lowest':>8}")
        for name, width, n, dr, da, first in suspect:
            print(f"  {name:<26}{width:>7}{n:>9}{dr:>18}{first:>8}")

        print("""
A run of bits no result ever sets, beside operands that set every bit, means the answers
were produced in something narrower than the format. The `lowest` column is where the run
starts, and it is 23 in binary64, fp128_e15m112 and gf32 alike -- three independent
formats agreeing on the boundary of a binary32 significand.

That is a shape, not a diagnosis. Reconstructing the arithmetic failed: binary64_div is
not binary64 division (46 of 384) and not binary32 division widened either (0 of 384). The
generator belongs to another line, and a guess dressed as a cause would be worse than the
open question.""")

    if verbose:
        print(f"\n  {'pack':<26}{'width':>7}{'dead r':>8}{'dead ab':>9}")
        for name, width, n, dr, da, first in rows:
            print(f"  {name:<26}{width:>7}{dr:>8}{da:>9}")

    return 1 if suspect else 0


def self_check() -> int:
    """Two controls, because this check can fail in both directions.

    A pack known to be healthy must report zero dead result bits, or the measurement is
    finding structure that is not there. And a synthetic pack whose results are truncated
    must be caught, or it is finding nothing at all.
    """
    healthy = os.path.join(VEC, "fp32_e8m23_add.json")
    got = scan(healthy)
    clean = got is not None and got[2] <= got[3]
    print(f"  fp32_e8m23_add: dead result bits {got[2]}, dead operand bits {got[3]}"
          f" -> not flagged: {clean}")

    # Truncate every result to its top half and require the check to notice.
    doc = json.load(open(healthy, encoding="utf-8"))
    vectors = doc["vectors"]
    forged = {"vectors": [{"a": v["a"], "b": v["b"],
                           "result": v["result"] & ~0xFFFF} for v in vectors]}
    tmp = healthy + ".selfcheck"
    try:
        open(tmp, "w", encoding="utf-8").write(json.dumps(forged))
        g2 = scan(tmp)
    finally:
        os.remove(tmp)
    caught = g2 is not None and g2[2] > g2[3]
    print(f"  the same pack with 16 result bits cleared: dead {g2[2]} vs {g2[3]}"
          f" -> flagged: {caught}")

    ok = clean and caught
    print(f"\nself-check: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        raise SystemExit(self_check())
    raise SystemExit(main())
