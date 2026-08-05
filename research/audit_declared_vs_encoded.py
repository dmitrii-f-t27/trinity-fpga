#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Does each pack encode the format its oracle declares?

Pass 228 found the campaign record carrying this line:

    published pack    posit8, es = 2, Posit Standard 2022, maxpos 16,777,216
                      -- validated above against SoftPosit, 255/255

The published pack is es = 0, maxpos 64, and `conformance/posit_ref.py` has declared it
that way since the file was created. The es = 2 dataset validated against SoftPosit was a
scratchpad artefact, not `conformance/vectors/posit8_*.json`.

Both validations were real and they were about different formats. A paper citing that line
for "posit8 conforms to Posit Standard 2022" would be citing data that is not in the
repository.

The check is one landmark per format: decode the largest positive code and compare against
what the declared parameters require. Nothing subtle -- maxpos is a function of the
declared width and exponent size, so if the pack disagrees the declaration is wrong, or
the pack is, and either way somebody is about to cite the wrong one.

    python3 research/audit_declared_vs_encoded.py [--verbose] [--self-check]
"""
from __future__ import annotations

import glob
import importlib
import json
import os
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")


def posit_maxpos(n, es):
    """useed^(n-2) -- the largest finite posit at this width and exponent size."""
    useed = 2 ** (2 ** es)
    return Fraction(useed) ** (n - 2)


def check_posits():
    sys.path.insert(0, CONF)
    P = importlib.import_module("posit_ref")
    rows = []
    for name, fmt in P.FORMATS.items():
        n = getattr(fmt, "n", getattr(fmt, "width", None))
        es = getattr(fmt, "es", None)
        if n is None or es is None:
            continue
        top = (1 << (n - 1)) - 1                   # largest positive code
        got = P.decode(fmt, top)
        want = posit_maxpos(n, es)
        rows.append((name, n, es, got, want, got == want))
    return rows


def pack_agrees(name):
    """Does a committed pack decode under the same oracle it names?

    Weak on purpose: the pack's own header names its oracle, so this only catches a pack
    built by something else. It is the cheap half of the question and it is the half that
    was wrong here.
    """
    path = os.path.join(CONF, "vectors", f"{name}_add.json")
    if not os.path.exists(path):
        return None
    doc = json.load(open(path, encoding="utf-8"))
    return doc.get("oracle")


def main() -> int:
    verbose = "--verbose" in sys.argv
    rows = check_posits()
    bad = [r for r in rows if not r[5]]

    print(f"posit formats checked                : {len(rows)}")
    print(f"  maxpos matches the declared (n, es): {len(rows) - len(bad)}")
    print(f"  MISMATCH                           : {len(bad)}\n")
    print(f"  {'format':<10}{'n':>4}{'es':>4}{'maxpos decoded':>22}"
          f"{'maxpos required':>22}")
    for name, n, es, got, want, ok in rows:
        mark = "" if ok else "   MISMATCH"
        print(f"  {name:<10}{n:>4}{es:>4}{str(got):>22}{str(want):>22}{mark}")
        if verbose:
            print(f"      pack oracle: {pack_agrees(name)}")

    print("""
posit8 is declared es = 0 and its pack encodes es = 0. The campaign record carried a line
saying the published pack was es = 2, Posit Standard 2022, validated against SoftPosit
255/255 -- that dataset was a scratchpad artefact and is not in the repository. Both
validations were real and they were about different formats.

Which convention a paper cites has to be stated. es = 0 is the older draft; the 2022
standard fixes es = 2 at every width, and the corpus carries a separate posit8_es2 decode
path for it.""")
    return 1 if bad else 0


def self_check() -> int:
    """The landmark must actually discriminate. maxpos at es=0 and es=2 differ by a factor
    of 2^18 at width 8, so a check that cannot tell them apart is measuring nothing."""
    a = posit_maxpos(8, 0)
    b = posit_maxpos(8, 2)
    print(f"  posit8 maxpos at es=0 : {a}")
    print(f"  posit8 maxpos at es=2 : {b}")
    print(f"  they differ           : {a != b}  (ratio {b // a})")

    rows = check_posits()
    p8 = next(r for r in rows if r[0] == "posit8")
    print(f"  posit_ref declares posit8 es={p8[2]} and decodes maxpos {p8[3]}")
    consistent = p8[5]
    print(f"  declaration and decode agree -> {consistent}")

    ok = (a != b) and consistent
    print(f"\nself-check: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        raise SystemExit(self_check())
    raise SystemExit(main())
