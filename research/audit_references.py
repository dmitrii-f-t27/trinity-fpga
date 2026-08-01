#!/usr/bin/env python3
"""Extract a paper's bibliography from its arXiv HTML rendering.

Paper B's references were audited by hand across passes 5 and 46 and 8 of 20 turned
out to carry a wrong title, wrong authors, or both -- including the companion-paper
self-citation. Paper A's bibliography has never been checked at all.

Resolving each entry still needs judgement, so this only does the mechanical half:
pull the entries out verbatim, and flag the shapes that were wrong last time.

    curl -sSL https://arxiv.org/html/<id>v<n> -o paper.html
    python3 research/audit_references.py paper.html

The heuristics below are LEADS, not verdicts -- the same discipline the numeric
sweeps use. Every flag has to be resolved by reading the actual work.
"""
from __future__ import annotations

import html
import re
import sys


def strip_tags(s: str) -> str:
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return " ".join(html.unescape(s).split())


def extract(path: str) -> list[str]:
    raw = open(path, encoding="utf-8", errors="replace").read()

    # arXiv's HTML renders each entry as <li class="ltx_bibitem" ...>
    items = re.findall(r'<li[^>]*class="[^"]*ltx_bibitem[^"]*"[^>]*>(.*?)</li>',
                       raw, flags=re.S | re.I)
    if items:
        return [strip_tags(i) for i in items]

    # fallback: a bibliography section with paragraph-per-entry
    m = re.search(r'(<section[^>]*bibliography.*?</section>)', raw, flags=re.S | re.I)
    if not m:
        return []
    return [strip_tags(p) for p in
            re.findall(r"<p[^>]*>(.*?)</p>", m.group(1), flags=re.S | re.I)]


SUSPECT = [
    (r"\bet\s+al\b.*\bet\s+al\b", "two 'et al' in one entry"),
    (r"^\s*\[\d+\]\s*[A-Z][a-z]+\s*,?\s*$", "entry is little more than a number"),
    (r"\b(TODO|TBD|XXX|FIXME|placeholder|Anonymous)\b", "placeholder text"),
    (r"\b(19|20|21|22|23|24|25|26)\d{2}\b(?!.*\b(19|20|21|22|23|24|25|26)\d{2}\b)", None),
]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[0])
        return 2
    entries = extract(sys.argv[1])
    if not entries:
        print("no bibliography found -- is this the HTML rendering?")
        return 1

    print(f"references found: {len(entries)}\n")
    for i, e in enumerate(entries, 1):
        text = e if len(e) < 400 else e[:400] + " …"
        print(f"[{i:>2}] {text}")

        flags = []
        if not re.search(r"\b(19|20)\d{2}\b|\b2[0-9]{3}\b", e):
            flags.append("no year")
        # Authors appear as "Surname, I." OR "I. Surname" OR "Surname et al."
        # A first version tested only the first form and produced 13 false flags on
        # a bibliography that was fine -- initials-first is the commoner style.
        if not re.search(r"[A-Z][a-z]+,\s*[A-Z]\.|[A-Z]\.\s*[A-Z]?\.?\s*[A-Z][a-z]+"
                         r"|[A-Z][a-z]+\s+et\s+al", e):
            flags.append("no recognisable author list")
        if re.search(r"\b(TODO|TBD|XXX|FIXME|placeholder|Anonymous)\b", e, re.I):
            flags.append("placeholder text")
        if len(e) < 40:
            flags.append("suspiciously short")
        if flags:
            print(f"     LEAD: {'; '.join(flags)}")
        print()

    print("Flags are leads, not verdicts. Paper B's defects were wrong TITLES and")
    print("wrong AUTHORS on entries that looked perfectly well-formed -- no")
    print("heuristic finds those. Each entry still has to be resolved against the")
    print("actual work it claims to cite.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
