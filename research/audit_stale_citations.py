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
    direct = os.path.join(ROOT, "specs", "numeric", name)
    if os.path.exists(direct):
        return direct
    hits = glob.glob(os.path.join(ROOT, "specs", "**", name), recursive=True)
    return hits[0] if hits else None


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

    checks = sorted(glob.glob(os.path.join(ROOT, "research", "*.py")))
    cited: dict[str, set[str]] = {}
    for f in checks:
        text = open(f, encoding="utf-8", errors="replace").read()
        for name in set(CITE.findall(text)):
            cited.setdefault(name, set()).add(os.path.basename(f))

    marked, missing, clean = [], [], 0
    for name, users in sorted(cited.items()):
        path = find_spec(name)
        if path is None:
            missing.append((name, users))
            continue
        text = open(path, encoding="utf-8", errors="replace").read()
        marks = sorted({m.group(1).upper() for m in MARKER.finditer(text)})
        if marks:
            marked.append((name, marks, users))
        else:
            clean += 1

    print(f"COVERAGE: {len(cited)} distinct .t27 specs cited by "
          f"{len(checks)} checks")
    print(f"  cite a spec with no retraction marker : {clean}")
    print(f"  cite a spec that carries one          : {len(marked)}")
    print(f"  cite a spec that cannot be found      : {len(missing)}\n")

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
