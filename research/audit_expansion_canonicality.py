#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Are the double_double / quad_double packs made of valid expansions?

Every other format in this corpus is canonical or not according to its *bits*. These two
are different: a `double_double` is a pair of binary64 values whose sum is the number, and
the pair is only a double-double if it is **nonoverlapping** -- each limb must be the
correctly-rounded binary64 of the exact sum of itself and everything below it. Shewchuk
calls this a nonoverlapping expansion; Hida, Li and Bailey's QD library calls it
renormalized and requires it of every input.

Two encodings can therefore hold the same value with one of them not a member of the
format at all, and no amount of comparing decoded values will notice.

    python3 research/audit_expansion_canonicality.py [--verbose] [--self-check]

Exit 0 when every operand and every result in the packs is a valid expansion.

WHAT THIS FOUND, AND WHAT IT DID NOT
------------------------------------
It found nothing wrong: 0 of 9,276 operands and 0 of 4,638 results are non-canonical.
That is a real answer and it deserves its reason, because the reason is an accident.

For formats wider than 64 bits, `generate_vectors.gen_pairs` draws operands with
`_rand_value_raw`, which encodes a random *value* rather than drawing random *bits*. Its
docstring gives the motive plainly -- raw-random operands would demand `pow2(huge)` and
hang. Every operand therefore arrives through `encode`, and `encode` emits renormalized
expansions, so canonicality is guaranteed by a decision made for speed.

The flip side is the part worth writing down: **no vector in the corpus exercises a
non-canonical expansion**. A hardware unit or a library handed an unrenormalized pair --
which is exactly what a caller who built one by hand would produce -- can diverge from
this oracle without a single vector disagreeing. The property holds; the domain is
untested; the two are not the same claim.

The first version of this file reported 80% of operands as non-canonical. Its limb order
was inverted: `encode(1.0)` yields limbs `[0x3ff0000000000000, 0x0]`, so limb 0 -- the one
at bit position 0 -- is the MOST significant, which the decoder's own docstring words the
other way round. The check now validates itself against `encode` before it reports
anything, which is the cheapest way to catch an inverted convention.
"""
from __future__ import annotations

import glob
import importlib.util
import json
import os
import random
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")


def load(name):
    p = os.path.join(CONF, f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def limbs(fmt, raw):
    """Most-significant first. See the module docstring: limb 0 sits at bit 0."""
    return [(raw >> (64 * i)) & ((1 << 64) - 1) for i in range(fmt.n_limbs)]


def canonical(E, fmt, raw):
    """True / False / None, where None means a limb is Inf or NaN.

    None is not False. An expansion containing a special is judged by
    research/audit_special_coverage.py, and folding it in here would count the same
    encoding twice under two different rules.
    """
    ls = limbs(fmt, raw)
    vals = []
    for l in ls:
        d = E._decode_binary64(l)
        if isinstance(d, E.Special):
            return None
        vals.append(d)
    for i in range(len(ls) - 1):
        tail = sum(vals[i + 1:], Fraction(0))
        if E._encode_binary64(vals[i] + tail) != ls[i]:
            return False
    return True


def validate_predicate(E) -> bool:
    """Whatever `encode` produces must be canonical. If this fails, the predicate has an
    inverted convention and every number it goes on to print is about itself."""
    rng = random.Random(7)
    vals = [Fraction(1), Fraction(1, 3), Fraction(2, 7), Fraction(10 ** 20, 3),
            Fraction(-355, 113), Fraction(2) ** 60 + Fraction(1, 3)]
    vals += [Fraction(rng.randrange(1, 10 ** 12), rng.randrange(1, 10 ** 12))
             for _ in range(20)]
    for fname, fmt in E.FORMATS.items():
        for v in vals:
            if canonical(E, fmt, E.encode(fmt, v)) is not True:
                print(f"  PREDICATE IS WRONG: encode({fname}, {v}) is called "
                      f"non-canonical")
                return False
    print(f"  predicate agrees with encode() on {len(vals)} values "
          f"x {len(E.FORMATS)} formats")
    return True


def main() -> int:
    verbose = "--verbose" in sys.argv
    E = load("extended_ref")

    if not validate_predicate(E):
        return 1

    tot_ops = tot_res = nc_ops = nc_res = spec = 0
    rows = []
    for path in sorted(glob.glob(os.path.join(CONF, "vectors",
                                              "*double_*.json"))):
        name = os.path.basename(path)
        fname = name.rsplit("_", 1)[0]
        fmt = E.FORMATS.get(fname)
        if fmt is None:
            continue
        vectors = json.load(open(path, encoding="utf-8"))["vectors"]
        o = r = s = 0
        for x in vectors:
            for k in ("a", "b"):
                c = canonical(E, fmt, int(x[k], 16))
                tot_ops += 1
                if c is None:
                    s += 1
                elif not c:
                    o += 1
                    if verbose and o <= 3:
                        print(f"      {name}: operand {x[k]}")
            c = canonical(E, fmt, int(x["expected"], 16))
            tot_res += 1
            if c is False:
                r += 1
        nc_ops += o
        nc_res += r
        spec += s
        rows.append((name, len(vectors), o, r, s))

    print(f"\n  {'pack':<26}{'vectors':>9}{'op !canon':>11}"
          f"{'res !canon':>12}{'special':>9}")
    for name, n, o, r, s in rows:
        print(f"  {name:<26}{n:>9}{o:>11}{r:>12}{s:>9}")
    print(f"  {'TOTAL':<26}{'':>9}{nc_ops:>11}{nc_res:>12}{spec:>9}")
    print(f"\n  {tot_ops} operands and {tot_res} results checked")

    print("""
A clean result here is not coverage. Operands for formats wider than 64 bits are drawn by
encoding a random VALUE, not by drawing random BITS -- generate_vectors._rand_value_raw,
chosen so wide formats do not have to compute pow2(huge). Everything therefore arrives
through encode(), and encode() renormalizes, so no vector can be non-canonical and none
ever exercises what happens when one is.

An implementation handed an unrenormalized pair -- what a caller who assembled one by hand
would produce -- can diverge from this oracle with every vector still agreeing.""")
    return 1 if (nc_ops or nc_res) else 0


def self_check() -> int:
    """Negative control. Build a pair that holds a correct value through limbs that
    overlap, and require the predicate to reject it. A canonicality check that accepts
    everything reports a clean corpus for free."""
    E = load("extended_ref")
    fmt = E.FORMATS["double_double"]

    ok_raw = E.encode(fmt, Fraction(1, 3))
    good = canonical(E, fmt, ok_raw)

    # 1.0 split as 0.5 + 0.5: the sum is exactly right, and fl(0.5 + 0.5) is 1.0, not
    # 0.5, so the leading limb does not absorb its own tail. A valid value; not a valid
    # expansion.
    half = E._encode_binary64(Fraction(1, 2))
    forged = half | (half << 64)
    bad = canonical(E, fmt, forged)
    value_is_right = E.decode(fmt, forged) == 1

    print(f"  encode(1/3) is canonical            -> {good}")
    print(f"  0.5 + 0.5 decodes to                -> {E.decode(fmt, forged)}")
    print(f"  ...and is rejected as an expansion  -> {bad is False}  "
          f"{'ok' if bad is False else 'THE PREDICATE ACCEPTS ANYTHING'}")
    print(f"  so value and membership differ here -> {value_is_right and bad is False}")

    passed = (good is True) and (bad is False) and value_is_right
    print(f"\nself-check: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        raise SystemExit(self_check())
    raise SystemExit(main())
