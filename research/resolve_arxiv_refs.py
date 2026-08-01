#!/usr/bin/env python3
"""Resolve each arXiv-cited reference and compare the cited title to the real one.

This is the check that found Paper B's defects: 8 of 20 entries carried a wrong
title, wrong authors, or both, and every one of them LOOKED well-formed. No
formatting heuristic finds that class -- only fetching the work does.

Paper A cites 33 works, most with an arXiv identifier, so most of it is checkable
mechanically.

    curl -sSL https://arxiv.org/html/<id>v<n> -o paper.html
    python3 research/resolve_arxiv_refs.py paper.html

Comparison is on normalised title tokens, and a difference is reported as a LEAD.
Subtitles, series names and honest abbreviations all produce differences that are
not defects; a wrong paper produces one that is. The output shows both titles so
the distinction can be made by reading rather than by threshold.
"""
from __future__ import annotations

import html
import re
import subprocess
import sys
import time


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    return " ".join(html.unescape(s).split())


def entries(path: str) -> list[str]:
    raw = open(path, encoding="utf-8", errors="replace").read()
    items = re.findall(r'<li[^>]*class="[^"]*ltx_bibitem[^"]*"[^>]*>(.*?)</li>',
                       raw, flags=re.S | re.I)
    return [strip_tags(i) for i in items]


def norm(t: str) -> set[str]:
    t = re.sub(r"[^a-z0-9 ]", " ", t.lower())
    stop = {"a", "an", "the", "of", "for", "and", "on", "in", "to", "with", "at",
            "its", "own", "by"}
    return {w for w in t.split() if w and w not in stop}


def fetch_all(ids: list[str]) -> dict[str, tuple[str, str]]:
    """One request for every id.

    A first version queried each id separately with a half-second pause and got 20
    of 23 back empty -- arXiv throttles rapid repeat queries, and the result read
    like a bibliography full of dead references when it was nothing of the kind.
    The API takes a comma-separated id_list, so one request is both correct and
    the polite thing to do.
    """
    url = ("https://export.arxiv.org/api/query?max_results=200&id_list="
           + ",".join(ids))
    try:
        out = subprocess.check_output(["curl", "-sS", "--max-time", "90", url],
                                      text=True)
    except subprocess.CalledProcessError:
        return {}

    found: dict[str, tuple[str, str]] = {}
    for chunk in out.split("<entry>")[1:]:
        def grab(tag):
            m = re.search(rf"<{tag}>(.*?)</{tag}>", chunk, re.S)
            return " ".join(m.group(1).split()) if m else ""

        idm = re.search(r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5})", grab("id"))
        if not idm:
            continue
        authors = re.findall(r"<name>(.*?)</name>", chunk, re.S)
        found[idm.group(1)] = (grab("title"),
                               "; ".join(a.strip() for a in authors[:4]))
    return found


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: resolve_arxiv_refs.py <paper.html>")
        return 2

    rows = entries(sys.argv[1])
    cited_ids = []
    for e in rows:
        m = re.search(r"arXiv:\s*([0-9]{4}\.[0-9]{4,5})", e)
        if m:
            cited_ids.append(m.group(1))
    resolved = fetch_all(cited_ids)

    checked = clean = leads = unresolved = 0

    for i, e in enumerate(rows, 1):
        m = re.search(r"arXiv:\s*([0-9]{4}\.[0-9]{4,5})", e)
        if not m:
            continue
        aid = m.group(1)
        checked += 1

        cited = re.search(r"[“\"']([^”\"']{6,200})[”\"']", e)
        cited_title = cited.group(1).strip() if cited else ""

        real_title, real_authors = resolved.get(aid, ("", ""))

        if not real_title:
            unresolved += 1
            print(f"[{i:>2}] arXiv:{aid}  UNRESOLVED (no entry returned)")
            continue

        a, b = norm(cited_title), norm(real_title)
        overlap = len(a & b) / max(1, len(a | b))
        if overlap >= 0.6:
            clean += 1
            continue

        leads += 1
        print(f"[{i:>2}] arXiv:{aid}   token overlap {overlap:.0%}")
        print(f"     cited : {cited_title}")
        print(f"     actual: {real_title}")
        print(f"     authors: {real_authors}")
        print()

    print(f"\nentries with an arXiv id : {checked}")
    print(f"  titles agree            : {clean}")
    print(f"  LEADS (differ)          : {leads}")
    print(f"  unresolved              : {unresolved}")
    print(f"entries without an arXiv id, not checkable this way: "
          f"{len(rows) - checked}")
    print("\nA LEAD is not a defect. Abbreviated titles, dropped subtitles and")
    print("series names all lower the overlap honestly. Read both strings before")
    print("concluding anything -- Paper B's real defects were entries pointing at a")
    print("DIFFERENT WORK, which is obvious once both titles are side by side.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
