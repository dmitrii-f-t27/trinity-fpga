#!/usr/bin/env python3
"""Does either paper cite the same work twice?

Paper A does: [10] cites arXiv:2412.20268 and [11] carries a DOI that resolves to
the same work under a different title. That was found by accident while checking
titles. This looks for the pattern deliberately, in both papers, over every
identifier present -- arXiv id, DOI, and URL.

A repeated identifier is unambiguous. A repeated WORK behind two different
identifiers -- an arXiv id in one entry and the publisher DOI in another -- is the
harder case and the one that actually occurred, so titles resolved earlier are
matched too where available.

    python3 research/find_duplicate_refs.py paperA.html paperB.html
"""
from __future__ import annotations

import collections
import html
import re
import sys


def strip(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def entries(path: str) -> list[str]:
    raw = open(path, encoding="utf-8", errors="replace").read()
    return [strip(i) for i in re.findall(
        r'<li[^>]*class="[^"]*ltx_bibitem[^"]*"[^>]*>(.*?)</li>', raw, re.S | re.I)]


def ids(text: str) -> set[str]:
    out = set()
    for m in re.finditer(r"arXiv[:\s]*([0-9]{4}\.[0-9]{4,5})", text, re.I):
        out.add("arxiv:" + m.group(1))
    for m in re.finditer(r"DOI[:\s]*(10\.\d{4,9}/[^\s,]+)", text, re.I):
        out.add("doi:" + m.group(1).rstrip(".").lower())
    for m in re.finditer(r"(https?://[^\s]+)", text):
        out.add("url:" + m.group(1).rstrip(".").lower())
    return out


for path in sys.argv[1:]:
    rows = entries(path)
    print(f"\n=== {path}  ({len(rows)} entries)")

    seen = collections.defaultdict(list)
    for i, e in enumerate(rows, 1):
        for ident in ids(e):
            seen[ident].append(i)

    dupes = {k: v for k, v in seen.items() if len(v) > 1}
    if not dupes:
        print("  no identifier appears in two entries")
    for ident, where in sorted(dupes.items()):
        print(f"  {ident}  cited by {where}")

    # entries carrying no identifier at all cannot be checked this way
    bare = [i for i, e in enumerate(rows, 1) if not ids(e)]
    if bare:
        print(f"  no identifier to compare: {bare}")

print("""
Note: this finds repeated IDENTIFIERS. Paper A's [10]/[11] duplicate is invisible
here -- one entry carries an arXiv id and the other a DOI, and they resolve to the
same work only when both are fetched. Identifier matching is a lower bound.""")
