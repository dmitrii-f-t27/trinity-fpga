#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Does a tool that sweeps every oracle look up a name only some of them have?

Pass 191 found this in my own work. `research/audit_pack_vs_oracle.py` swept all eighteen
oracles and reached their arithmetic with a literal `getattr(mod, "format_add")`.
Seventeen modules have that name. `gf_ref` calls its entry points `gf_add` and `gf_mul`,
which `generate_vectors.MODULES` declares and the audit did not read. Every GoldenFloat
pack -- the widths the first paper is about -- fell into a NO ORACLE REACHABLE bucket and
was reported as unchecked, while the oracle sat there the whole time. The count of
unreachable packs was inflated by 54.

The shape is worth naming because it evades the obvious check. A name that resolves
*nowhere* is a crash, and someone fixes it the same day. A name that resolves *almost
everywhere* is silence: the sweep runs, the number comes out smaller, and nothing says
which modules fell out.

    python3 research/audit_hardcoded_lookups.py [--verbose] [--self-check]

WHAT IT DOES
------------
Statically finds `getattr(<anything>, "<literal>")` in research/ and conformance/, then
asks how many corpus modules actually have that attribute. Full coverage is fine. Zero
coverage is fine too -- that is a crash waiting to be found, not a silent gap. Partial
coverage is the finding.

A declaration already exists for the arithmetic entry points: the (module, add, mul,
family) tuples in generate_vectors.MODULES. Any sweep should read it rather than assume a
name, and a literal that matches some declared entry point but not all of them is flagged
with the modules it misses.
"""
from __future__ import annotations

import ast
import glob
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")

# Attribute names every module is expected to lack or have for structural reasons, where
# a partial answer is the correct answer rather than a gap.
BENIGN = {
    # Optional capabilities. A module either models the thing or does not, and the caller
    # is expected to branch on it -- that is the point of asking with getattr.
    "is_canonical", "Special", "nar", "has_inf", "nan_at_max_only", "signed",
    "n_limbs", "kind", "coeff_bits_big", "coeff_bits_small", "mant_bits", "exp_max",
    "exp_bits", "bias", "max_coeff", "width", "mask", "pos_zero", "neg_zero",
    "pos_inf", "neg_inf", "quiet_nan", "max_val", "min_val", "field_mask",
    "field_min", "explicit_int_bit", "min_exp_field", "base", "name", "vectors",
    "expected", "result", "FORMATS", "decode", "encode",
}


def corpus_modules():
    """The modules that actually present the oracle interface, and the ones that do not.

    Globbing *_ref.py and calling every match an oracle was the first version's mistake,
    and the control caught it: no attribute resolves on all eighteen, because gf_mx_ref
    has no FORMATS, no decode and no encode. It is a constants file wearing the suffix.
    Counting it as an oracle missing everything would make every literal look partial.

    An oracle is a module with FORMATS. The rest are returned separately so they are
    reported rather than silently dropped -- a module that stopped being an oracle by
    accident should be visible, not filtered away.
    """
    sys.path.insert(0, CONF)
    oracles, not_oracles = {}, {}
    for path in sorted(glob.glob(os.path.join(CONF, "*_ref.py"))):
        name = os.path.basename(path)[:-3]
        try:
            mod = importlib.import_module(name)
        except Exception as e:
            not_oracles[name] = f"import failed: {type(e).__name__}"
            continue
        if hasattr(mod, "FORMATS"):
            oracles[name] = mod
        else:
            missing = [a for a in ("FORMATS", "decode", "encode")
                       if not hasattr(mod, a)]
            not_oracles[name] = "no " + ", ".join(missing)
    return oracles, not_oracles


def declared_entry_points():
    """The (add, mul) names generate_vectors declares, per module."""
    sys.path.insert(0, CONF)
    try:
        G = importlib.import_module("generate_vectors")
    except Exception:
        return {}
    return {m: (a, mu) for m, a, mu, _f in G.MODULES}


def getattr_literals(path):
    """Every string literal used as the attribute name in getattr(x, "lit")."""
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
    except SyntaxError:
        return set()
    found = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "getattr" and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)):
            found.add(node.args[1].value)
    return found


def main() -> int:
    verbose = "--verbose" in sys.argv
    mods, not_oracles = corpus_modules()
    declared = declared_entry_points()
    entry_names = {n for pair in declared.values() for n in pair}

    rows, partial = [], []
    for path in sorted(glob.glob(os.path.join(ROOT, "research", "*.py"))
                       + glob.glob(os.path.join(CONF, "*.py"))):
        base = os.path.basename(path)
        if base == "audit_hardcoded_lookups.py":
            continue
        for lit in sorted(getattr_literals(path)):
            if lit in BENIGN:
                continue
            have = [n for n, m in mods.items() if hasattr(m, lit)]
            missing = [n for n in mods if n not in have]
            rows.append((base, lit, len(have), len(mods)))
            # Partial coverage is the finding. Zero is a crash someone will hit; full is
            # fine. A declared entry point that only some modules answer to is the
            # pass-191 shape exactly.
            if have and missing and (lit in entry_names or lit.startswith("format_")):
                partial.append((base, lit, have, missing))

    print(f"getattr literals examined            : {len(rows)}")
    print(f"  oracle modules in the corpus       : {len(mods)}")
    for n, why in sorted(not_oracles.items()):
        print(f"    {n}: not an oracle -- {why}")
    print(f"  literals resolving on SOME but not all : {len(partial)}\n")

    if partial:
        print("PARTIAL RESOLUTION -- the sweep runs, the count comes out smaller, and")
        print("nothing says which modules fell out:")
        for base, lit, have, missing in partial:
            print(f"  {base:<34} getattr(..., {lit!r})")
            print(f"      missing from: {', '.join(sorted(missing))}")
            if lit in entry_names:
                who = [m for m, pair in declared.items() if lit in pair]
                print(f"      declared in MODULES for: {', '.join(sorted(who))}"
                      f" -- read it instead of assuming")
        print()

    if verbose:
        for base, lit, have, total in rows:
            print(f"  {base:<34} {lit:<24} {have}/{total}")

    print("""
A name that resolves nowhere is a crash and gets fixed the same day. A name that resolves
almost everywhere is silence. This check only reports the second, and only for names the
corpus already declares somewhere -- generate_vectors.MODULES carries the arithmetic entry
points per module, so a sweep never needs to guess one.""")
    return 1 if partial else 0


def self_check() -> int:
    """The control has to prove the finder still finds. Write a throwaway module that
    getattrs an entry point only some oracles have, and require a flag; then confirm a
    name every module has is not flagged."""
    probe = os.path.join(ROOT, "research", "_hardcoded_probe.py")
    mods, not_oracles = corpus_modules()
    open(probe, "w", encoding="utf-8").write(
        'def f(mod):\n'
        '    return getattr(mod, "format_add", None)\n'
        '\n'
        'def g(mod):\n'
        '    return getattr(mod, "decode", None)\n')
    try:
        lits = getattr_literals(probe)
        have_fa = [n for n, m in mods.items() if hasattr(m, "format_add")]
        miss_fa = [n for n in mods if n not in have_fa]
        have_dec = [n for n, m in mods.items() if hasattr(m, "decode")]
        miss_dec = [n for n in mods if n not in have_dec]
    finally:
        os.remove(probe)

    found_both = {"format_add", "decode"} <= lits
    partial_fa = bool(have_fa and miss_fa)
    full_dec = not miss_dec
    print(f"  both literals extracted from the probe -> {found_both}")
    print(f"  'format_add' resolves on {len(have_fa)}/{len(mods)}, "
          f"missing {sorted(miss_fa)} -> partial: {partial_fa}")
    print(f"  'decode' resolves on {len(have_dec)}/{len(mods)} -> not flagged: {full_dec}")
    print(f"      excluded as not-an-oracle: "
          f"{', '.join(sorted(not_oracles)) or 'none'}")
    print(f"  probe file removed -> {not os.path.exists(probe)}")
    ok = found_both and partial_fa and full_dec
    print(f"\nself-check: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        raise SystemExit(self_check())
    raise SystemExit(main())
