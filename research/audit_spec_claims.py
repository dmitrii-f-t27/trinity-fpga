#!/usr/bin/env python3
"""Find absence and uniqueness claims in the .t27 specs that are NOT marked superseded.

Pass 82's fifth instance of "one fact, two files, updated in one" was found in a
spec, outside the area being searched. specs/numeric/ holds 20+ files this campaign
wrote and has never swept.

The discrimination that matters: these specs deliberately keep refuted claims as
history, marked with SUPERSEDED_BY, `correction`, `retracted` or a "what was wrong"
field. Those are the honesty record, not defects. What matters is a claim standing
as CURRENT that is no longer true.

So a hit is reported only when its enclosing block carries no supersession marker.

    python3 research/audit_spec_claims.py specs/numeric/*.t27
"""
from __future__ import annotations

import glob
import os
import re
import sys

ABSENCE = [
    r"there is no\b", r"does not exist", r"not publicly (?:verifiable|available)",
    r"no (?:public|release feed|such)\b", r"nobody (?:else|has)\b",
    r"never (?:checked|verified|run|examined)\b", r"cannot be (?:found|reached)",
]
# "the first attempt/version/run/classifier" is narrative, not a uniqueness claim,
# and matching it bare produced most of the noise on the first sweep.
UNIQUENESS = [
    r"\bthe only\b",
    r"\bthe first\b(?!\s+(?:attempt|version|run|classifier|pass|reading|thing|"
    r"time|line|entry|DOI|sampler|draft))",
    r"\bno other\b", r"\bunprecedented\b",
    r"\bonly \w+ (?:ships|publishes|has|does)\b",
]

# a block carrying any of these is history, deliberately kept
MARKERS = re.compile(
    r"SUPERSEDED_BY|superseded|retracted|correction|what_was_wrong|"
    r"as_first_written|first_reading|what_i_(?:did|wrote|said)|"
    r"was wrong|no longer|amended|void", re.I)

BLOCK = re.compile(r"^(\w+)\s+([A-Z_0-9]+)\s*\{", re.M)


def blocks(text):
    """(name, body, start_line) for each top-level block."""
    out = []
    marks = list(BLOCK.finditer(text))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((m.group(2), text[m.start():end],
                    text[:m.start()].count("\n") + 1))
    return out


def main() -> int:
    paths = sys.argv[1:] or sorted(glob.glob("specs/numeric/*.t27"))
    total = flagged = shielded = 0

    for path in paths:
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for name, body, line in blocks(text):
            hits = []
            for pat in ABSENCE + UNIQUENESS:
                for m in re.finditer(pat, body, re.I):
                    a = max(0, m.start() - 60)
                    hits.append(" ".join(body[a:m.end() + 80].split()))
            if not hits:
                continue
            total += len(hits)
            if MARKERS.search(body):
                shielded += len(hits)
                continue
            flagged += len(hits)
            print(f"{os.path.basename(path)}:{line}  block {name}")
            for h in hits[:3]:
                print(f"    …{h[:118]}…")
            print()

    print(f"claims found        : {total}")
    print(f"  inside a marked-superseded block (history, not a defect): {shielded}")
    print(f"  standing as current, unmarked                          : {flagged}")
    print("\nAn unmarked hit is a lead, not a verdict -- some absences are simply")
    print("true. Each still has to be checked against what is known now.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
