#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RETRACTED. gf16_plus_ref is not a second implementation.

Pass 194 read its first import:

    from gf_ref import FORMATS, decode, encode, gf_mul, Special

`gf16_plus_ref.decode is gf_ref.decode` is True. So is encode, so is FORMATS, so is
Special -- the same objects, not merely equivalent ones. This file compared a function
with itself and reported that it agreed.

What passes 192 and 193 claimed:

    9,041 decodes, 0 disagreements, against an independent implementation
    159,430 add/mul results, 0 disagreements, against an independent implementation

Both are void as independence claims. The decode comparison is entirely vacuous. The
arithmetic comparison is nearly so: `gf_ref.gf_add` is decode -> specials -> signed zero
-> exact sum -> encode, and the "independent" adder written for pass 193 is the same
recipe over the same decode and encode. It confirmed that two spellings of one algorithm
agree, which was never in doubt.

**GoldenFloat has no independent second witness.** It is where it was before pass 192, and
saying so is worth more than the number that was there instead.

The lesson is about the control, not the claim. Pass 192's self-check required the
takum_ref/takum_log_ref pair to be REJECTED -- a real control against comparing unrelated
formats -- and had nothing asserting the two modules were distinct code. Guarding against
the wrong pair while never checking the pair is two things is exactly the shape this
campaign keeps finding elsewhere.

`research/audit_witness_independence.py` now checks that: any module claiming to witness
another must not re-export its functions. Both files here refuse to run rather than print
a comforting zero.
"""

from __future__ import annotations

import glob
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")


def load():
    sys.path.insert(0, CONF)
    return (importlib.import_module("gf_ref"),
            importlib.import_module("gf16_plus_ref"))


def pack_codes(name):
    """Every distinct code appearing anywhere in this format's packs, either schema."""
    codes = set()
    for path in glob.glob(os.path.join(CONF, "vectors", f"{name}_*.json")):
        doc = json.load(open(path, encoding="utf-8"))
        for v in doc.get("vectors", []):
            for k in ("a", "b", "expected", "result"):
                x = v.get(k)
                if isinstance(x, str):
                    codes.add(int(x, 16))
                elif isinstance(x, int):
                    codes.add(x)
    return codes


def compare(A, B, name, codes):
    f1, f2 = A.FORMATS[name], B.FORMATS[name]
    n = ok = 0
    first = None
    for c in sorted(codes):
        try:
            v1, v2 = A.decode(f1, c), B.decode(f2, c)
        except Exception:
            continue
        n += 1
        if str(v1) == str(v2):
            ok += 1
        elif first is None:
            first = (c, str(v1)[:28], str(v2)[:28])
    return n, ok, first


def _independence_or_die():
    """Refuse to run. Left as executable code rather than deleted, so the retraction is
    visible where the claim was made and cannot be quietly resurrected."""
    import importlib
    import sys
    sys.path.insert(0, CONF)
    A = importlib.import_module("gf_ref")
    B = importlib.import_module("gf16_plus_ref")
    shared = [n for n in ("decode", "encode", "FORMATS", "Special")
              if getattr(A, n, None) is getattr(B, n, None)]
    print("RETRACTED -- gf16_plus_ref re-exports gf_ref; see the module docstring.")
    print(f"  shared objects: {', '.join(shared)}")
    print("  GoldenFloat has no independent second witness.")
    return 2


def main() -> int:
    return _independence_or_die()


def _old_main() -> int:
    verbose = "--verbose" in sys.argv
    A, B = load()

    shared = [n for n in A.FORMATS if n in B.FORMATS]
    tot = agree = 0
    rows = []
    for name in shared:
        codes = pack_codes(name)
        if not codes:
            rows.append((name, 0, 0, None))
            continue
        n, ok, first = compare(A, B, name, codes)
        tot += n
        agree += ok
        rows.append((name, n, ok, first))

    print(f"widths declared by both decoders     : {len(shared)}")
    print(f"  distinct codes cross-checked       : {tot}")
    print(f"  DISAGREEMENTS                      : {tot - agree}\n")
    for name, n, ok, first in rows:
        flag = "ok" if n == ok else f"{n - ok} DISAGREE"
        note = "" if n else "   (no packs)"
        print(f"  {name:<9}{n:>8} codes   {flag}{note}")
        if first and verbose:
            print(f"      first: {first[0]:#x} -> {first[1]} vs {first[2]}")

    print("""
Decode only. gf16_plus_ref has no add or mul, so this compares the values the packs name
and says nothing about whether the arithmetic on them is right.

Shared format names are not evidence of a shared format. takum_ref and takum_log_ref also
share names and are different families -- 3 of 256 codes agree at takum8. What licenses
the comparison here is that the two decoders agree on every code, not that the keys match.""")
    return 1 if agree != tot else 0


def self_check() -> int:
    """Two controls.

    The comparison must catch a decoder that has drifted, or a clean sweep means nothing.
    And it must still reject the takum pair, or it would be licensing comparisons on the
    strength of matching dictionary keys -- the mistake passes 144 to 146 made.
    """
    A, B = load()
    fmt = "gf8"
    codes = pack_codes(fmt) or set(range(256))
    n, ok, _ = compare(A, B, fmt, codes)
    clean = n == ok
    print(f"  gf8: {ok}/{n} agree -> {clean}")

    # Perturb one decode and require the comparison to see it.
    f2 = B.FORMATS[fmt]
    real = B.decode
    victim = sorted(codes)[len(codes) // 2]

    def drifted(f, c):
        v = real(f, c)
        return v + 1 if (c == victim and not isinstance(v, B.Special)) else v

    B.decode = drifted
    try:
        n2, ok2, first = compare(A, B, fmt, codes)
    finally:
        B.decode = real
    caught = ok2 == n2 - 1
    print(f"  with one code perturbed: {ok2}/{n2} -> caught: {caught}")

    # The takum pair must NOT look like a match.
    sys.path.insert(0, CONF)
    T = importlib.import_module("takum_ref")
    L = importlib.import_module("takum_log_ref")
    same = 0
    for c in range(256):
        try:
            same += str(T.decode(T.FORMATS["takum8"], c)) == \
                    str(L.decode(L.FORMATS["takum8"], c))
        except Exception:
            pass
    rejected = same < 250
    print(f"  takum_ref vs takum_log_ref at takum8: {same}/256 agree -> "
          f"correctly NOT a second witness: {rejected}")

    ok_all = clean and caught and rejected
    print(f"\nself-check: {'PASS' if ok_all else 'FAIL'}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        raise SystemExit(_independence_or_die())
    raise SystemExit(main())
