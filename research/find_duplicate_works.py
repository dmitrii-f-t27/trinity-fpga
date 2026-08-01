#!/usr/bin/env python3
"""Find references that cite the SAME WORK under different identifiers.

find_duplicate_refs.py groups by identifier and cannot see Paper A's [10]/[11]
duplicate: one entry carries an arXiv id, the other a publisher DOI, and they are
the same paper only once both are resolved. That is the one shape the method misses
by construction, and it already produced a real finding.

This resolves every identifier to a canonical title first, then groups by the title.
Different identifier types collapse to the same work when they should.

    python3 research/find_duplicate_works.py paperA.html paperB.html
"""
from __future__ import annotations

import collections
import html
import json
import re
import subprocess
import sys
import time


def strip(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def entries(path: str) -> list[str]:
    raw = open(path, encoding="utf-8", errors="replace").read()
    return [strip(i) for i in re.findall(
        r'<li[^>]*class="[^"]*ltx_bibitem[^"]*"[^>]*>(.*?)</li>', raw, re.S | re.I)]


def arxiv_titles(ids):
    if not ids:
        return {}
    url = ("https://export.arxiv.org/api/query?max_results=100&id_list="
           + ",".join(sorted(set(ids))))
    out = subprocess.check_output(["curl", "-sS", "--max-time", "90", url],
                                  text=True)
    found = {}
    for chunk in out.split("<entry>")[1:]:
        m = re.search(r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5})", chunk)
        t = re.search(r"<title>(.*?)</title>", chunk, re.S)
        if m and t:
            found[m.group(1)] = " ".join(t.group(1).split())
    return found


def doi_title(doi):
    try:
        out = subprocess.check_output(
            ["curl", "-sS", "--max-time", "45", "-H",
             "User-Agent: t27-audit (mailto:admin@t27.ai)",
             f"https://api.crossref.org/works/{doi}"],
            text=True, stderr=subprocess.DEVNULL)
        return (json.loads(out)["message"].get("title") or [""])[0]
    except Exception:
        return ""


def canon(t: str) -> str:
    t = re.sub(r"[^a-z0-9 ]", " ", t.lower())
    stop = {"a", "an", "the", "of", "for", "and", "on", "in", "to", "with", "at",
            "its", "by", "from", "is", "are"}
    return " ".join(sorted(w for w in t.split() if w and w not in stop))


for path in sys.argv[1:]:
    rows = entries(path)
    print(f"\n=== {path}  ({len(rows)} entries)")

    ax = {}
    for i, e in enumerate(rows, 1):
        m = re.search(r"arXiv[:\s]*([0-9]{4}\.[0-9]{4,5})", e, re.I)
        if m:
            ax[i] = m.group(1)
    titles = arxiv_titles(list(ax.values()))

    resolved = {}
    for i, e in enumerate(rows, 1):
        if i in ax and ax[i] in titles:
            resolved[i] = ("arXiv:" + ax[i], titles[ax[i]])
            continue
        m = re.search(r"DOI[:\s]*(10\.\d{4,9}/[^\s,]+)", e, re.I)
        if m:
            t = doi_title(m.group(1).rstrip("."))
            time.sleep(0.4)
            if t:
                resolved[i] = ("DOI:" + m.group(1).rstrip("."), t)

    groups = collections.defaultdict(list)
    for i, (ident, title) in resolved.items():
        groups[canon(title)].append((i, ident, title))

    dupes = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"  resolved to a title: {len(resolved)} of {len(rows)}")
    if not dupes:
        print("  no two entries resolve to the same work")
    for _, members in dupes.items():
        print(f"\n  DUPLICATE — the same work cited {len(members)} times:")
        print(f"    \"{members[0][2]}\"")
        for i, ident, _ in members:
            print(f"      [{i}]  via {ident}")

print("""
Unresolved entries -- books, standards, forum posts -- cannot be compared this way
and are not claimed to be free of duplicates.""")
