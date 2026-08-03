#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Is a claimed second witness actually a second implementation?

Passes 192 and 193 cross-validated GoldenFloat against `conformance/gf16_plus_ref.py` and
reported 9,041 decodes and 159,430 arithmetic results with zero disagreements. Pass 194
read that module's first import:

    from gf_ref import FORMATS, decode, encode, gf_mul, Special

`gf16_plus_ref.decode is gf_ref.decode` -- the same object, not an equivalent one. The
comparison was a function against itself, and of course it agreed. Both claims are
retracted; GoldenFloat has no independent second witness.

The failure was in the control, not the claim. Pass 192's self-check required the
`takum_ref` / `takum_log_ref` pair to be REJECTED, which is a real guard against comparing
two different formats that share names. It had nothing asserting the pair being compared
was two things at all. Guarding one direction and not the other is the shape this campaign
keeps finding in other people's checks.

This file is the missing direction. For any two modules offered as witnesses of each
other it asks three questions, cheapest first:

    1. identity     do they expose the same function objects?
    2. provenance   does one import those names from the other?
    3. text         are the implementations byte-identical after stripping comments?

Any yes disqualifies the pair. A no to all three is not proof of independence -- two
authors can converge, and a shared helper module is invisible here -- but it rules out the
way this corpus actually failed.

    python3 research/audit_witness_independence.py [--verbose] [--self-check]
"""
from __future__ import annotations

import ast
import glob
import importlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")

# The names a witness comparison actually leans on.
WITNESS_API = ("decode", "encode", "FORMATS", "Special")


def module_path(name):
    return os.path.join(CONF, f"{name}.py")


def imports_from(name, other):
    """Names `name` imports directly from `other`, read from the source, not at runtime.

    Static, because a module that re-exports under an alias would still be caught, and
    because a runtime check cannot say *where* an identical object came from.
    """
    path = module_path(name)
    if not os.path.exists(path):
        return set()
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
    except SyntaxError:
        return set()
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == other:
            out |= {a.asname or a.name for a in node.names}
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name == other:
                    out.add(a.asname or a.name)
    return out


def strip_comments(src):
    src = re.sub(r'"""(?:.|\n)*?"""', "", src)
    src = re.sub(r"#.*", "", src)
    return re.sub(r"\s+", " ", src).strip()


def verdict(a_name, b_name):
    """(independent: bool, reasons: list[str])."""
    sys.path.insert(0, CONF)
    reasons = []
    try:
        A = importlib.import_module(a_name)
        B = importlib.import_module(b_name)
    except Exception as e:
        return False, [f"one module does not import: {type(e).__name__}"]

    shared = [n for n in WITNESS_API
              if getattr(A, n, None) is not None
              and getattr(A, n, None) is getattr(B, n, None)]
    if shared:
        reasons.append(f"same objects: {', '.join(shared)}")

    for src, dst in ((b_name, a_name), (a_name, b_name)):
        names = imports_from(src, dst)
        overlap = names & set(WITNESS_API)
        if overlap:
            reasons.append(f"{src} imports {', '.join(sorted(overlap))} from {dst}")

    pa, pb = module_path(a_name), module_path(b_name)
    if os.path.exists(pa) and os.path.exists(pb):
        if strip_comments(open(pa, encoding="utf-8").read()) == \
           strip_comments(open(pb, encoding="utf-8").read()):
            reasons.append("implementations are textually identical")

    return (not reasons), reasons


def main() -> int:
    verbose = "--verbose" in sys.argv
    mods = sorted(os.path.basename(p)[:-3]
                  for p in glob.glob(os.path.join(CONF, "*_ref.py")))

    # Every pair that declares an overlapping format name is a candidate witness pair --
    # that is how gf16_plus_ref was found, and how it should have been disqualified.
    sys.path.insert(0, CONF)
    live = {}
    for m in mods:
        try:
            mod = importlib.import_module(m)
            if hasattr(mod, "FORMATS"):
                live[m] = set(mod.FORMATS)
        except Exception:
            pass

    pairs, bad = [], []
    names = sorted(live)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            shared_fmts = live[a] & live[b]
            if not shared_fmts:
                continue
            ok, reasons = verdict(a, b)
            pairs.append((a, b, len(shared_fmts), ok, reasons))
            if not ok:
                bad.append((a, b, len(shared_fmts), reasons))

    print(f"module pairs sharing at least one format name : {len(pairs)}")
    print(f"  NOT independent                             : {len(bad)}\n")
    for a, b, n, reasons in bad:
        print(f"  {a} / {b}   ({n} shared format names)")
        for r in reasons:
            print(f"      {r}")
    if verbose:
        for a, b, n, ok, reasons in pairs:
            if ok:
                print(f"  {a} / {b}: {n} shared names, no shared code found")

    print("""
Sharing format names makes a pair a CANDIDATE witness, never a witness. Two things have to
hold: the formats must actually be the same -- takum_ref and takum_log_ref share four names
and agree on 3 of 256 codes -- and the implementations must actually be two. Passes 192 and
193 checked the first and assumed the second.

A clean result here is not proof of independence. Two authors can converge on the same
algorithm, and a helper module both import is invisible to all three questions. It rules
out the way this corpus actually failed, which is worth exactly that much.""")
    return 1 if bad else 0


def self_check() -> int:
    """The known positive and the known negative.

    gf16_plus_ref/gf_ref must be rejected -- that is the case this file exists for. And
    two modules that genuinely do not share code must not be, or the check rejects
    everything and means nothing.
    """
    ok1, why1 = verdict("gf_ref", "gf16_plus_ref")
    print(f"  gf_ref / gf16_plus_ref -> independent: {ok1}  (must be False)")
    for r in why1:
        print(f"      {r}")

    ok2, why2 = verdict("decimal_ref", "posit_ref")
    print(f"  decimal_ref / posit_ref -> independent: {ok2}  (must be True)")
    for r in why2:
        print(f"      {r}")

    passed = (not ok1) and ok2
    print(f"\nself-check: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        raise SystemExit(self_check())
    raise SystemExit(main())
