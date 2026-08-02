#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Which encodings can a vector never contain, and why?

`generate_vectors.gen_pairs` draws its random operands two different ways:

    width <= 32 (and every integer format)   random RAW BITS
    width >  32                              random VALUES, encoded

The second line is `_rand_value_raw`, and its docstring gives the motive plainly: raw
bits for a wide format would demand `pow2(huge)` and hang. It is a decision about cost.

It is also, silently, a decision about coverage. Every operand for a wide format arrives
through `encode`, so **no vector can hold a code outside the image of encode** -- no
non-canonical encoding, no reserved pattern, no redundant cohort member that the encoder
does not choose. Those codes exist, hardware and libraries will be handed them, and
nothing in the corpus asks what happens.

Pass 188 found this by asking why pass 185's canonicality defect showed up where it did:

    decimal32   width 32, raw-random    485,760 non-canonical codes per sign
                                        20 of them are in the pack -> the defect was found
    decimal64   width 64, value-driven  1,258,999,068,426,240 non-canonical codes
                                        0 in the pack
    decimal128  width 128, value-driven 2,980,742,146,337,069,071,326,240,823,050,240
                                        0 in the pack

The same defect was in all three. It was findable in exactly the one that sits on the
width boundary. That is not a testing strategy, it is a coincidence, and it is worth
knowing which formats are on the wrong side of it.

    python3 research/audit_operand_reachability.py [--verbose] [--self-check]

Exit 0 when every wide format either has structurally-built operands covering the codes
outside encode's image, or has no such codes to cover.
"""
from __future__ import annotations

import glob
import importlib
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")

RAW_RANDOM_MAX_WIDTH = 32          # mirrors gen_pairs; read from it in check_cut()


def load(name):
    p = os.path.join(CONF, f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def check_cut(G) -> int:
    """Read the cut out of gen_pairs rather than trusting the constant above.

    A number copied from code into a checker is a number that goes stale the first time
    the code changes, and this campaign has already been burnt by exactly that.
    """
    import inspect
    src = inspect.getsource(G.gen_pairs)
    import re
    m = re.search(r"elif width <= (\d+):", src)
    return int(m.group(1)) if m else RAW_RANDOM_MAX_WIDTH


def noncanonical_population(mod, fmt, family):
    """How many codes lie outside what the format defines, where that is countable.

    Returns (count, description) or None when the format has no such class, or when
    counting it needs knowledge this file does not have. None is not zero and is reported
    as its own column.
    """
    if family == "decimal":
        # BID case B reaches a coefficient of 2^(coeff_bits_big-3)*5 - 1 while the format
        # stops at max_coeff. Everything between is non-canonical: IEEE 754-2008 3.5.2
        # gives it the value zero.
        reach = ((0b100 << (fmt.coeff_bits_big - 3))
                 | ((1 << (fmt.coeff_bits_big - 3)) - 1))
        n = max(0, reach - fmt.max_coeff)
        return (n, "non-canonical BID case-B coefficients, per sign") if n else None
    if family == "legacy" and getattr(fmt, "kind", "") == "x87":
        # unnormals: exponent non-zero with the explicit integer bit clear.
        n = (fmt.exp_max - 1) * (1 << (fmt.mant_bits - 1))
        return (n, "unnormals / pseudo-infinities, per sign")
    if family == "legacy" and getattr(fmt, "kind", "") == "vax":
        return (1 << fmt.mant_bits, "reserved operands (sign 1, exponent 0)")
    if family == "extended":
        return (None, "overlapping expansions -- uncountable here, see "
                      "audit_expansion_canonicality.py")
    return None


def is_canonical_fn(mod):
    return getattr(mod, "is_canonical", None)


def main() -> int:
    verbose = "--verbose" in sys.argv
    sys.path.insert(0, CONF)
    G = load("generate_vectors")
    cut = check_cut(G)

    print(f"operand sampling cut, read from gen_pairs : width <= {cut} uses raw bits\n")

    rows, uncovered = [], []
    for mod_name, _a, _m, family in G.MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue
        canon = is_canonical_fn(mod)
        for fname, fmt in mod.FORMATS.items():
            width = G.get_width(fmt)
            if G.is_int_family(fmt) or width <= cut:
                continue                      # raw bits reach everything
            pop = noncanonical_population(mod, fmt, family)
            if pop is None:
                continue
            count, what = pop

            # How many operands in this format's packs are outside encode's image?
            found = 0
            checked = 0
            if canon is not None:
                for path in glob.glob(os.path.join(CONF, "vectors",
                                                   f"{fname}_*.json")):
                    for x in json.load(open(path, encoding="utf-8"))["vectors"]:
                        for k in ("a", "b"):
                            checked += 1
                            if canon(fmt, int(x[k], 16)) is False:
                                found += 1
            rows.append((fname, family, width, count, what, found, checked))
            if count is not None and count > 0 and found == 0:
                uncovered.append((fname, count, what))

    print(f"  {'format':<14}{'w':>5}{'codes outside the format':>28}"
          f"{'in packs':>10}")
    for fname, family, width, count, what, found, checked in rows:
        c = f"{count:,}" if isinstance(count, int) else "not countable here"
        print(f"  {fname:<14}{width:>5}{c:>28}{found:>10}")
        if verbose:
            print(f"      {what}; {checked} operands checked")

    if uncovered:
        print(f"\nUNREACHABLE: {len(uncovered)} formats have codes their own definition")
        print("excludes, and not one appears in any vector:")
        for fname, count, what in uncovered:
            print(f"  {fname:<14} {count:,} {what}")

    print("""
This is a coverage report, not a defect list. Every one of these codes decodes to
something well-defined -- the point is that nothing checks it, and nothing would notice
if it stopped being well-defined.

The cut is read out of gen_pairs each run rather than copied here, so moving it moves this
report with it.""")
    return 1 if uncovered else 0


def self_check() -> int:
    """The report has to change when the corpus does. Confirm both directions on a format
    whose answer is known: decimal32 sits below the cut and has non-canonical operands in
    its packs; decimal64 sits above it and has none, despite having 2.6 billion times as
    many such codes."""
    sys.path.insert(0, CONF)
    G = load("generate_vectors")
    D = importlib.import_module("decimal_ref")
    cut = check_cut(G)

    out = {}
    for name in ("decimal32", "decimal64"):
        fmt = D.FORMATS[name]
        n = 0
        for path in glob.glob(os.path.join(CONF, "vectors", f"{name}_*.json")):
            for x in json.load(open(path, encoding="utf-8"))["vectors"]:
                for k in ("a", "b"):
                    if D.is_canonical(fmt, int(x[k], 16)) is False:
                        n += 1
        out[name] = (fmt.width, n)

    below = out["decimal32"][0] <= cut and out["decimal32"][1] > 0
    above = out["decimal64"][0] > cut and out["decimal64"][1] == 0
    print(f"  cut read from gen_pairs                 : width <= {cut}")
    print(f"  decimal32 (width {out['decimal32'][0]}, below the cut)     : "
          f"{out['decimal32'][1]} non-canonical operands in its packs")
    print(f"  decimal64 (width {out['decimal64'][0]}, above the cut)     : "
          f"{out['decimal64'][1]}")
    print(f"  below-the-cut format reaches them  -> {below}")
    print(f"  above-the-cut format does not      -> {above}")
    ok = below and above
    print(f"\nself-check: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        raise SystemExit(self_check())
    raise SystemExit(main())
