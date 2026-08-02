#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Does any check still rest on a spec that has been retracted?

Pass 162 found `audit_generated_packs.py` reporting a "TAKUM-CLASS SIGNATURE", citing
`specs/numeric/negation_invariant.t27` as establishing the defect, and concluding that
three packs "must not be published". Line 8 of that spec, written eleven passes earlier,
retracts exactly that reading.

Three packs were held back on a basis their own cited authority had withdrawn.

That is the third way a check can be wrong, and the hardest to notice: it runs, reports
confidently, and cites a source. The first two -- a check that cannot see (pass 157) and
a check that measures the wrong thing (passes 156, 158-161) -- announce themselves
eventually, because the numbers look strange. A stale citation looks like diligence.

So this reads every `.t27` a check cites, looks for a retraction marker in it, and says
which checks depend on one. It does not decide whether the dependence is fatal -- a
docstring mentioning a withdrawn result is a different matter from an exit code keyed on
it -- so both are reported and the reader judges.

    python3 research/audit_stale_citations.py [--self-check]
"""
from __future__ import annotations

import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CITE = re.compile(r"(?:specs/[\w./-]+/)?([\w-]+\.t27)")
MARKER = re.compile(r"^\s*//\s*(RETRACTED|SUPERSEDED|WITHDRAWN|CORRECTED)\b.*$",
                    re.M | re.I)


def find_spec(name: str):
    """Anywhere in the tree, not just under specs/.

    The first version looked only in specs/**, and reported gf8.t27,
    goldenfloat_family.t27 and mac.t27 as missing. They are in t27/specs/ -- a vendored
    copy of the sibling repository -- and were never missing at all. Three of four
    "NOT FOUND" results were the search path, not the tree.
    """
    direct = os.path.join(ROOT, "specs", "numeric", name)
    if os.path.exists(direct):
        return direct
    for pattern in (os.path.join(ROOT, "specs", "**", name),
                    os.path.join(ROOT, "**", name)):
        hits = [h for h in glob.glob(pattern, recursive=True)
                if os.sep + ".git" + os.sep not in h]
        if hits:
            return hits[0]
    return in_sibling_repo(name)


def in_sibling_repo(name: str):
    """Resolve against gHashTag/t27, which several documents cite by name.

    Pass 164 reported formats_catalog.t27 as existing "nowhere in the tree or on any
    branch" and called it the one genuine gap. It is in t27 at
    specs/numeric/formats_catalog.t27, 32,652 bytes, exactly where all eight citing
    documents say it is. The earlier probes missed it because `contents/specs` lists
    only the top level of that directory and `gh search code` depends on indexing.

    That was the third time in three passes that a "missing" result was the search and
    not the tree. So this asks the repository directly, and when it cannot ask -- no
    network, no gh, no auth -- it says so instead of concluding absence.
    """
    import subprocess
    for path in (f"specs/numeric/{name}", f"specs/{name}", f"conformance/{name}"):
        try:
            r = subprocess.run(
                ["gh", "api", f"repos/gHashTag/t27/contents/{path}", "--jq", ".name"],
                capture_output=True, text=True, timeout=60)
        except Exception:
            return UNCHECKABLE
        if r.returncode == 0 and r.stdout.strip():
            return f"gHashTag/t27:{path}"
    return None


UNCHECKABLE = object()


def self_check() -> int:
    """The marker pattern must fire on the line that started this. If
    negation_invariant.t27 ever stops matching, the scan has gone blind and a clean
    result from a blind scan is worth less than no scan."""
    p = find_spec("negation_invariant.t27")
    if p is None:
        print("  negation_invariant.t27 not found -- cannot self-check")
        return 1
    text = open(p, encoding="utf-8", errors="replace").read()
    m = MARKER.search(text)
    ok = bool(m) and "RETRACTED" in m.group(1).upper()
    print(f"  negation_invariant.t27 marker detected -> {ok}")
    if m:
        print(f"      {m.group(0).strip()[:78]}")
    print(f"\nself-check: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--self-check" in sys.argv:
        return self_check()

    # Pass 164 widened this. Reading only research/*.py saw 2 retracted specs and 4
    # citations. The tree has 4, and the costly ones were elsewhere: specs cite each
    # other 11 times, and research/*.md -- the documents an author reads -- cite them
    # 5 times. One of those told the author to quote a withdrawn figure.
    checks = sorted(glob.glob(os.path.join(ROOT, "research", "*.py"))
                    + glob.glob(os.path.join(ROOT, "research", "*.md"))
                    + glob.glob(os.path.join(ROOT, "specs", "**", "*.t27"),
                                recursive=True))
    cited: dict[str, set[str]] = {}
    for f in checks:
        text = open(f, encoding="utf-8", errors="replace").read()
        for name in set(CITE.findall(text)):
            if name == os.path.basename(f):        # a spec naming itself
                continue
            cited.setdefault(name, set()).add(os.path.basename(f))

    marked, missing, clean = [], [], 0
    elsewhere, unreachable = [], []
    for name, users in sorted(cited.items()):
        path = find_spec(name)
        if path is UNCHECKABLE:
            unreachable.append((name, users))
            continue
        if path is None:
            missing.append((name, users))
            continue
        if isinstance(path, str) and path.startswith("gHashTag/t27:"):
            elsewhere.append((name, path, users))
            continue
        text = open(path, encoding="utf-8", errors="replace").read()
        marks = sorted({m.group(1).upper() for m in MARKER.finditer(text)})
        if marks:
            marked.append((name, marks, users))
        else:
            clean += 1

    print(f"COVERAGE: {len(cited)} distinct .t27 specs cited by "
          f"{len(checks)} files (checks, author documents and specs)")
    print(f"  cite a spec with no retraction marker : {clean}")
    print(f"  cite a spec that carries one          : {len(marked)}")
    print(f"  cite a spec that lives in gHashTag/t27: {len(elsewhere)}")
    print(f"  cite a spec that cannot be found      : {len(missing)}")
    if unreachable:
        print(f"  could NOT be checked (no network/gh)  : {len(unreachable)}")
    print()
    for name, path, users in elsewhere:
        print(f"  ELSEWHERE  {name}  ->  {path}")
        print(f"             cited by {', '.join(sorted(users))}")

    for name, users in missing:
        print(f"  NOT FOUND  {name}")
        print(f"             cited by {', '.join(sorted(users))}")

    for name, marks, users in marked:
        print(f"  {'/'.join(marks):<12} {name}")
        print(f"               cited by {', '.join(sorted(users))}")

    if marked:
        print("""
Citing a retracted spec is not automatically wrong. A file may cite one to say the
finding was withdrawn, which is exactly what a corrected check should do. What must not
happen is a check RESTING on it -- keying an exit code, a verdict, or a publication
block on a claim the source has taken back.

Read each pairing above and ask which it is. Pass 162's example took eleven passes to
notice because the check ran, reported confidently, and cited a source.""")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
