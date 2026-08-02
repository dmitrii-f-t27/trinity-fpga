#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A second witness for GoldenFloat arithmetic, not just for its decode.

Pass 192 found `conformance/gf16_plus_ref.py`: a second, independent implementation of the
same seventeen GoldenFloat widths, sitting in the repository unused, agreeing with
`gf_ref` on 9,041 decodes. That covered the values the packs name and said nothing about
the operations on them, because `gf16_plus_ref` has no add or mul.

It does have `decode` and `encode`, and that is enough. Correctly-rounded arithmetic is
"take the exact result, then round it to the format" -- a specification, not an
implementation -- so an adder built on this module's own decode and encode shares no line
of code with `gf_ref.gf_add`. That is what makes it a witness rather than a restatement.

    python3 research/crossval_gf_second_arithmetic.py [--verbose] [--self-check]

WHAT THE FIRST VERSION GOT WRONG
--------------------------------
It reported 2,471 disagreements out of 159,430, and every single one was its own. The
naive construction computes `Fraction(a) + Fraction(b)` and encodes it -- and a Fraction
has no signed zero, so `(-0) + (-0)` came back `+0` and `x * 0` lost the sign of the
product. All 510 gf8 multiplication disagreements were exactly that, and so was the one in
addition. The packs were right in every case.

The sign of a zero is not a rounding question and cannot be recovered from the exact
value, so it is carried separately here, the way every oracle in this corpus already does:
the sign of a product is the exclusive-or of the operand signs, and a sum of two zeros
keeps their sign only when they agree.
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


def load():
    sys.path.insert(0, CONF)
    return importlib.import_module("gf16_plus_ref")


def signed_zero(fmt, sign):
    return fmt.neg_zero if sign else fmt.pos_zero


def build(B):
    """add and mul over B's own decode/encode. Returns (add, mul) or (None, None)."""
    Special = B.Special

    def sign_of(fmt, raw):
        return (raw >> (fmt.width - 1)) & 1

    def add(fmt, a_raw, b_raw):
        a, b = B.decode(fmt, a_raw), B.decode(fmt, b_raw)
        if isinstance(a, Special) or isinstance(b, Special):
            return None                       # specials are a separate question
        sa, sb = sign_of(fmt, a_raw), sign_of(fmt, b_raw)
        if a == 0 and b == 0:
            # -0 + -0 is -0; every other pairing of zeros is +0 under round-to-nearest.
            return signed_zero(fmt, 1 if (sa and sb) else 0)
        return B.encode(fmt, Fraction(a) + Fraction(b))

    def mul(fmt, a_raw, b_raw):
        a, b = B.decode(fmt, a_raw), B.decode(fmt, b_raw)
        if isinstance(a, Special) or isinstance(b, Special):
            return None
        sign = sign_of(fmt, a_raw) ^ sign_of(fmt, b_raw)
        if a == 0 or b == 0:
            # The sign of a zero product is the xor of the operand signs and cannot be
            # recovered from the exact value -- Fraction(0) has no sign. Dropping this
            # was the whole of the first version's 2,471 "disagreements".
            return signed_zero(fmt, sign)
        return B.encode(fmt, Fraction(a) * Fraction(b))

    return add, mul


def pack_vectors(name, op):
    path = os.path.join(CONF, "vectors", f"{name}_{op}.json")
    if not os.path.exists(path):
        return []
    doc = json.load(open(path, encoding="utf-8"))
    out = []
    for v in doc.get("vectors", []):
        def num(x):
            return int(x, 16) if isinstance(x, str) else x
        e = v.get("expected", v.get("result"))
        out.append((num(v["a"]), num(v["b"]), num(e)))
    return out


def run(B, verbose=False):
    add, mul = build(B)
    rows = []
    tot = agree = skipped = 0
    for name, fmt in B.FORMATS.items():
        n = ok = sk = 0
        first = None
        for op, fn in (("add", add), ("mul", mul)):
            for a, b, e in pack_vectors(name, op):
                g = fn(fmt, a, b)
                if g is None:
                    sk += 1
                    continue
                n += 1
                if g == e:
                    ok += 1
                elif first is None:
                    first = (op, a, b, e, g)
        tot += n
        agree += ok
        skipped += sk
        rows.append((name, n, ok, sk, first))
    return rows, tot, agree, skipped


def main() -> int:
    verbose = "--verbose" in sys.argv
    B = load()
    rows, tot, agree, skipped = run(B, verbose)

    print(f"GoldenFloat widths with a second implementation : {len(rows)}")
    print(f"  add/mul results cross-checked                 : {tot}")
    print(f"  DISAGREEMENTS                                 : {tot - agree}")
    print(f"  skipped (a special operand)                   : {skipped}\n")
    for name, n, ok, sk, first in rows:
        flag = "ok" if n == ok else f"{n - ok} DISAGREE"
        print(f"  {name:<9}{n:>8} results   {flag}")
        if first and verbose:
            op, a, b, e, g = first
            print(f"      first: {a:#x} {op} {b:#x} -> pack {e:#x}, witness {g:#x}")

    print("""
Independent in the way that matters: the arithmetic here is built on gf16_plus_ref's own
decode and encode, so it shares no line with gf_ref.gf_add. What the two have in common is
the specification -- exact result, then round -- which is the thing being checked, not an
implementation detail being reused.

Specials are skipped, not passed. gf16_plus_ref and gf_ref agree on which codes ARE
special (pass 192, 9,041 decodes) but this file does not model NaN propagation, and
counting a skipped case as agreement is the substitution this campaign exists to catch.""")
    return 1 if agree != tot else 0


def self_check() -> int:
    """Three controls.

    The witness must reproduce the packs; it must catch a perturbed answer; and it must
    still get the sign of zero right, since getting that wrong is what made the first
    version report 2,471 defects that were its own.
    """
    B = load()
    add, mul = build(B)
    f = B.FORMATS["gf8"]

    rows, tot, agree, _ = run(B)
    clean = tot == agree
    print(f"  all widths: {agree}/{tot} agree -> {clean}")

    neg_zero, pos_zero = f.neg_zero, f.pos_zero
    z1 = add(f, neg_zero, neg_zero) == neg_zero
    z2 = add(f, neg_zero, pos_zero) == pos_zero
    one = B.encode(f, Fraction(1))
    neg_one = B.encode(f, Fraction(-1))
    z3 = mul(f, neg_one, pos_zero) == neg_zero
    z4 = mul(f, one, pos_zero) == pos_zero
    print(f"  (-0) + (-0) = -0 -> {z1}")
    print(f"  (-0) + (+0) = +0 -> {z2}")
    print(f"  (-1) * (+0) = -0 -> {z3}")
    print(f"  (+1) * (+0) = +0 -> {z4}")

    # Perturb the witness and require the comparison to notice.
    real = B.encode
    victim = [None]

    def drifted(fmt, v):
        r = real(fmt, v)
        if victim[0] is None and v != 0:
            victim[0] = r
            return r ^ 1
        return r

    B.encode = drifted
    try:
        _, t2, a2, _ = run(B)
    finally:
        B.encode = real
    caught = a2 < t2
    print(f"  one perturbed encode is caught -> {caught}")

    ok = clean and z1 and z2 and z3 and z4 and caught
    print(f"\nself-check: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        raise SystemExit(self_check())
    raise SystemExit(main())
