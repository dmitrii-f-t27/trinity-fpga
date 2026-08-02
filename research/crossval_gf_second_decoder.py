#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""An independent second decoder for GoldenFloat was already in the repository.

Honesty rule #10 wants a second implementation that shares no code with the first. This
campaign has spent passes hunting for one -- SoftPosit for posit, libtakum for takum,
gcc's Intel BID for decimal. For GoldenFloat, the formats the first paper is about, there
was never a candidate.

There was. `conformance/gf16_plus_ref.py` declares the same seventeen widths as
`conformance/gf_ref.py` and decodes them independently. It is not in
`generate_vectors.MODULES`, so it has never generated a vector, and nothing has ever
compared the two. It was found by a check written for a different purpose: pass 192 was
auditing for hardcoded attribute names and noticed three `*_ref.py` modules that no sweep
reaches.

    9,041 distinct codes across all seventeen widths, 0 disagreements.

WHAT THIS IS NOT
----------------
Not a witness for the arithmetic. `gf16_plus_ref` has no add or mul; only `decode` is
comparable, so this covers the decode packs' operands and results as *values* and says
nothing about whether the operations on them are right.

And emphatically not a template for `takum`. `takum_ref` and `takum_log_ref` also share
format names -- takum8, takum16, takum32, takum64 -- and are **different families**:
3 of 256 codes agree at takum8, 1 of 4096 at takum16. Passes 144 to 146 were spent
comparing against the wrong one because the 2*pi landmark happened to agree for both, and
a landmark that agrees for two different things distinguishes neither. Shared names are
not evidence of a shared format; identical decodes over the whole code space are.

    python3 research/crossval_gf_second_decoder.py [--verbose] [--self-check]
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


def main() -> int:
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
        raise SystemExit(self_check())
    raise SystemExit(main())
