#!/usr/bin/env python3
"""Resolve every DOI in a LaTeX bibliography and compare against what is cited.

All arXiv entries in all three GoldenFloat documents have been resolved (passes 63,
75, 84). The DOIs in main_ru.tex have not, and pass 74 established that a DOI is
exactly where a misattribution hides: Paper A's [11] looked perfectly well-formed
and pointed at a different paper.

Crossref answers for publisher DOIs; Zenodo DOIs live in DataCite, so both are
tried.

    python3 research/resolve_tex_dois.py main_ru.tex
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time

UA = "t27-reference-audit (mailto:admin@t27.ai)"


def norm(t: str) -> set[str]:
    t = re.sub(r"[^a-z0-9 ]", " ", t.lower())
    stop = {"a", "an", "the", "of", "for", "and", "on", "in", "to", "with", "at",
            "its", "by", "from", "is", "are"}
    return {w for w in t.split() if w and w not in stop}


def crossref(doi):
    try:
        out = subprocess.check_output(
            ["curl", "-sS", "--max-time", "45", "-H", f"User-Agent: {UA}",
             f"https://api.crossref.org/works/{doi}"],
            text=True, stderr=subprocess.DEVNULL)
        m = json.loads(out)["message"]
    except Exception:
        return None
    return ((m.get("title") or [""])[0],
            "; ".join(f"{a.get('given','')} {a.get('family','')}".strip()
                      for a in (m.get("author") or [])[:4]))


def datacite(doi):
    try:
        out = subprocess.check_output(
            ["curl", "-sS", "--max-time", "45", "-H", f"User-Agent: {UA}",
             f"https://api.datacite.org/dois/{doi}"],
            text=True, stderr=subprocess.DEVNULL)
        a = json.loads(out)["data"]["attributes"]
    except Exception:
        return None
    titles = a.get("titles") or [{}]
    return (titles[0].get("title", ""),
            "; ".join(c.get("name", "") for c in (a.get("creators") or [])[:4]))


def main() -> int:
    src = open(sys.argv[1], encoding="utf-8", errors="replace").read()
    items = re.split(r"\\bibitem", src)[1:]

    checked = agree = leads = unresolved = 0
    for n, it in enumerate(items, 1):
        m = re.search(r"(10\.\d{4,9}/[A-Za-z0-9./_()-]*?)[.,)\s]*$|"
                      r"(10\.\d{4,9}/[A-Za-z0-9./_()-]+)", it)
        if not m:
            continue
        doi = (m.group(1) or m.group(2)).rstrip(".)")
        checked += 1

        q = re.search(r"``(.+?)''|“(.+?)”", it, re.S)
        cited = " ".join((q.group(1) or q.group(2)).split()) if q else ""

        got = datacite(doi) if "zenodo" in doi.lower() else crossref(doi)
        if got is None:
            got = crossref(doi) or datacite(doi)
        time.sleep(0.4)

        if not got or not got[0]:
            unresolved += 1
            print(f"[{n:>2}] {doi}  DID NOT RESOLVE")
            continue
        real, authors = got
        if not cited:
            print(f"[{n:>2}] {doi}  no title in the entry")
            print(f"     actually: {real[:92]}\n")
            leads += 1
            continue
        ov = len(norm(cited) & norm(real)) / max(1, len(norm(cited) | norm(real)))
        if ov >= 0.6:
            agree += 1
            continue
        leads += 1
        print(f"[{n:>2}] {doi}   overlap {ov:.0%}")
        print(f"     cited   : {cited[:92]}")
        print(f"     actually: {real[:92]}")
        print(f"     authors : {authors}\n")

    print(f"\nentries with a DOI : {checked}")
    print(f"  titles agree     : {agree}")
    print(f"  LEADS            : {leads}")
    print(f"  unresolved       : {unresolved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
