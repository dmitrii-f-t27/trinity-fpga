#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Does any check decide what belongs by a list of names somebody typed?

Three times now, in checks written by the same hand:

    pass 183   wrapper_fsm_audit.py required `mx in (5, 6, 8)` and flagged every format
               wider than the three that existed when it was written -- 40 of 93.
    pass 205   verify_tier_e.py named cells from an alternation with no lns, no ibm_hfp,
               no ms_mbf, no double_double. 75 complete Tier-E chains reported as 34
               distinct cells instead of 48, and two of my own passes closed with the
               false statement that no LNS cell was in the ledger.
    pass 206   verify_wide_arithmetic.py selected wide GoldenFloat formats with
               ("gf32", "gf48", "gf64", "gf96", "gf128", "gf1024"), silently omitting
               gf256 and gf512.

A list of names is a snapshot of the corpus on the day it was typed. The corpus is
enumerable, so a check can ask it instead.

    python3 research/audit_name_allowlists.py [--verbose] [--self-check]

WHAT COUNTS AND WHAT DOES NOT
-----------------------------
Naming formats is normal and mostly fine. A self-test that runs three specific widths, a
docstring listing what a module covers, a table of expected values -- all of those name
formats and none of them is a snapshot, because nothing is being decided about input the
author has not seen.

The bad shape is narrow: a literal collection used to **decide membership** of a variable,
or a regex alternation of format names fed to `search`/`match`/`findall`. Then anything
outside the list is silently dropped, and the count comes out smaller with nothing saying
which fell out.

A first version of this file flagged any place mentioning three or more corpus format
names. That was 25 places and nearly all of them were fine -- which is the same
over-reporting this campaign keeps catching, in the check written to catch it.
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

MIN_NAMES = 3          # two names is a pair, not a list


def corpus_names():
    sys.path.insert(0, CONF)
    names = set()
    for path in sorted(glob.glob(os.path.join(CONF, "*_ref.py"))):
        try:
            mod = importlib.import_module(os.path.basename(path)[:-3])
        except Exception:
            continue
        names |= set(getattr(mod, "FORMATS", {}))
    return names


def classifiers(path, names):
    """(line, kind, matched_names) for every list that decides membership here."""
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
    except SyntaxError:
        return []
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Compare) and any(isinstance(o, ast.In) for o in n.ops):
            for cmp_ in n.comparators:
                if isinstance(cmp_, (ast.Tuple, ast.List, ast.Set)):
                    lits = {e.value for e in cmp_.elts
                            if isinstance(e, ast.Constant)
                            and isinstance(e.value, str)}
                    k = lits & names
                    if len(k) >= MIN_NAMES:
                        out.append((n.lineno, "membership test", sorted(k)))
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in ("search", "match", "fullmatch", "findall")):
            for a in n.args:
                if (isinstance(a, ast.Constant) and isinstance(a.value, str)
                        and "|" in a.value):
                    k = set(re.findall(r"\w+", a.value)) & names
                    if len(k) >= MIN_NAMES:
                        out.append((n.lineno, "regex classifier", sorted(k)))
    return out


def main() -> int:
    verbose = "--verbose" in sys.argv
    names = corpus_names()
    hits = []
    for path in sorted(glob.glob(os.path.join(ROOT, "research", "*.py"))
                       + glob.glob(os.path.join(CONF, "*.py"))):
        if os.path.basename(path) == "audit_name_allowlists.py":
            continue
        for line, kind, k in classifiers(path, names):
            missing = sorted(n for n in names if n not in k
                             and n.rstrip("0123456789") in
                             {x.rstrip("0123456789") for x in k})
            hits.append((os.path.relpath(path, ROOT), line, kind, k, missing))

    print(f"corpus format names                  : {len(names)}")
    print(f"  lists deciding membership by name  : {len(hits)}\n")
    for rel, line, kind, k, missing in hits:
        print(f"  {rel}:{line}  [{kind}]  {len(k)} names")
        print(f"      lists: {', '.join(k)}")
        if missing:
            print(f"      SAME FAMILY, NOT LISTED: {', '.join(missing)}")
        if verbose:
            print(f"      corpus has {len(names)} names in total")

    print("""
Naming a format is normal. Deciding membership by a typed list is the shape that goes
stale, because the corpus grows and the list does not, and nothing says which entries fell
out. Where the report shows SAME FAMILY, NOT LISTED, the list already has a gap today.

A first version of this file flagged every place mentioning three or more format names --
25 of them, nearly all fine. Over-reporting is the failure this campaign keeps finding,
and it found it here first.""")
    return 1 if any(h[4] for h in hits) else 0


def self_check() -> int:
    """The scan has to reject what it is supposed to reject and accept what it is not.

    Positive control: a file that tests membership against a list of format names must be
    flagged. Negative control: a file that merely iterates the same names must not.
    """
    names = corpus_names()
    sample = sorted(names)[:4]
    probe = os.path.join(ROOT, "research", "_allowlist_probe.py")

    bad_src = ("def f(x):\n"
               f"    return x in ({', '.join(repr(n) for n in sample)})\n")
    good_src = ("def g(mod):\n"
                f"    for n in ({', '.join(repr(n) for n in sample)}):\n"
                "        mod.check(n)\n")
    try:
        open(probe, "w", encoding="utf-8").write(bad_src)
        flagged = len(classifiers(probe, names)) > 0
        open(probe, "w", encoding="utf-8").write(good_src)
        not_flagged = len(classifiers(probe, names)) == 0
    finally:
        os.remove(probe)

    print(f"  membership test against {len(sample)} names -> flagged: {flagged}")
    print(f"  plain iteration over the same names -> flagged: {not not_flagged}")
    print(f"  probe removed -> {not os.path.exists(probe)}")
    ok = flagged and not_flagged
    print(f"\nself-check: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        raise SystemExit(self_check())
    raise SystemExit(main())
