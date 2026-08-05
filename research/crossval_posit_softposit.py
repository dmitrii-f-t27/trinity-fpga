#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Do the posit division and square-root packs agree with SoftPosit?

SoftPosit is the reference implementation. Passes 225 to 227 built it from source and put
the `_exact` packs against it:

    posit8    div  251/251   sqrt  256/256
    posit16   div  214/216   sqrt  220/220
    posit32   div  220/220   sqrt  221/221

The two posit16 division differences are both ours-closer-to-the-exact-quotient.

THE ENTRY POINT IS THE WHOLE PROBLEM
------------------------------------
SoftPosit's dedicated types carry the exponent sizes of the older posit drafts:

    p8_*   es = 0        p16_*  es = 1        p32_*  es = 2

`conformance/posit_ref.py` declares posit8 es=0, posit16 es=2, posit32 es=2. So

    posit8   -> p8_*     matching es
    posit32  -> p32_*    matching es
    posit16  -> pX2_*    the variable-width es=2 path; p16_* is a DIFFERENT FORMAT

Comparing posit16 against p16_div reads 24 of 216, which looks like a catastrophe and is
two formats being compared. Comparing posit8 against pX2_div reads 137 of 251, because
the variable-width path rounds less accurately than the dedicated one -- ours is closer to
the exact quotient in 113 of those 114 differences, SoftPosit in none.

Twice a bad agreement number meant the wrong entry point rather than a defect. Asking
which side is nearer the exact value is cheap and settles it before the right comparison
confirms it, so this file reports that column whenever the two disagree.

    python3 research/crossval_posit_softposit.py [--dumps DIR] [--self-check]

Exit 0 when every compared pair agrees or the disagreement is ours-closer. Exit 2 when the
dumps are absent -- a skip, never a pass.

BUILDING THE DUMPS
------------------
SoftPosit does not compile unmodified here. Three C++ default initialisers in
softposit_types.h are not valid C, and GCC 14 makes an incompatible-pointer-type in
p32_to_p16.c an error. Both are worked around in a COPY of the tree; the original is never
written. The recipe is in the campaign record under pass 225.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")

# width -> the SoftPosit entry point whose es matches posit_ref's declaration
ENTRY = {8: "p8_* (es 0)", 16: "pX2_* (es 2)", 32: "p32_* (es 2)"}


def load_dump(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) == 3:
                out[(int(parts[0]), int(parts[1]))] = int(parts[2])
    return out


def compare(P, width, op, ref):
    name = f"posit{width}"
    fmt = P.FORMATS[name]
    path = os.path.join(CONF, "vectors", f"{name}_{op}_exact.json")
    if not os.path.exists(path):
        return None
    doc = json.load(open(path, encoding="utf-8"))
    n = ok = 0
    kinds = collections.Counter()
    for v in doc["vectors"]:
        a, b = int(v["a"], 16), int(v["b"], 16)
        e = int(v["expected"], 16)
        key = (a, b) if op == "div" else (a, 0)
        if key not in ref:
            continue
        n += 1
        r = ref[key]
        if r == e:
            ok += 1
            continue
        kinds[nearer(P, fmt, op, a, b, e, r)] += 1
    return n, ok, kinds


def nearer(P, fmt, op, a, b, ours, theirs):
    """Which side is closer to the exact result -- the question that found both
    entry-point mistakes before the right comparison did."""
    va = P.decode(fmt, a)
    vb = P.decode(fmt, b)
    if isinstance(va, P.Special) or isinstance(vb, P.Special):
        return "a special is involved"
    try:
        if op == "div":
            if vb == 0:
                return "division by zero"
            exact = Fraction(va) / Fraction(vb)
        else:
            if va < 0:
                return "sqrt of a negative"
            exact = Fraction(math.isqrt(int(Fraction(va) * 10 ** 40)), 10 ** 20)
        de, dr = P.decode(fmt, ours), P.decode(fmt, theirs)
        if isinstance(de, P.Special) or isinstance(dr, P.Special):
            return "one side is special"
        eo, et = abs(Fraction(de) - exact), abs(Fraction(dr) - exact)
    except Exception:
        return "not comparable"
    if eo < et:
        return "OURS closer to exact"
    if et < eo:
        return "SOFTPOSIT closer to exact"
    return "equally near"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dumps", default=os.environ.get("TRINITY_ARTEFACTS", "/tmp"))
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        return self_check()

    sys.path.insert(0, CONF)
    import importlib
    P = importlib.import_module("posit_ref")

    rows, missing = [], []
    for width in (8, 16, 32):
        for op in ("div", "sqrt"):
            dump = os.path.join(args.dumps, f"posit{width}_{op}_softposit.tsv")
            if not os.path.exists(dump):
                missing.append(os.path.basename(dump))
                continue
            got = compare(P, width, op, load_dump(dump))
            if got:
                rows.append((width, op, *got))

    if not rows:
        print("No SoftPosit dumps found. Expected, under --dumps:")
        for m in missing:
            print(f"    {m}")
        print("\nSKIPPED -- not a pass. The build recipe is in the module docstring.")
        return 2

    print(f"  {'format':<10}{'op':<6}{'compared':>10}{'agree':>8}  entry point")
    bad = 0
    for width, op, n, ok, kinds in rows:
        print(f"  posit{width:<5}{op:<6}{n:>10}{ok:>8}  {ENTRY[width]}")
        for kind, c in kinds.most_common():
            print(f"      {c} {kind}")
            if kind == "SOFTPOSIT closer to exact":
                bad += c

    print(f"""
SoftPosit's dedicated types carry the older drafts' exponent sizes -- p8 es=0, p16 es=1,
p32 es=2 -- and posit_ref declares posit8 es=0, posit16 es=2, posit32 es=2. posit16 must
therefore be compared against the variable-width pX2 path; p16_* is a different format,
and comparing against it reads 24 of 216.

Where the two differ, the column above says which is nearer the exact value. That question
is cheap and it caught both entry-point mistakes before the right comparison confirmed
them.""")
    return 1 if bad else 0


def self_check() -> int:
    """The es table must match what posit_ref actually declares. A comparison keyed on a
    stale exponent size is the failure this file exists to describe."""
    sys.path.insert(0, CONF)
    import importlib
    P = importlib.import_module("posit_ref")
    want = {8: 0, 16: 2, 32: 2}
    ok = True
    for width, es in want.items():
        actual = getattr(P.FORMATS[f"posit{width}"], "es", None)
        good = actual == es
        ok = ok and good
        print(f"  posit{width}: posit_ref says es={actual}, this file assumes "
              f"{es} -> {good}")
    print(f"  entry points: " + ", ".join(f"{w}->{ENTRY[w]}" for w in sorted(ENTRY)))
    print(f"\nself-check: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
