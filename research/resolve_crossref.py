#!/usr/bin/env python3
"""Resolve the references that carry a DOI or ISBN rather than an arXiv id.

resolve_arxiv_refs.py checked 23 of Paper A's 33 entries. The other 10 are books,
journal articles and standards documents; Crossref answers for the DOIs, and the
rest have to be judged by eye.

Same discipline as the arXiv pass: a title difference is a LEAD, not a verdict.
Abbreviations and dropped subtitles lower the overlap honestly; a wrong work does
not.

    curl -sSL https://arxiv.org/html/<id>v<n> -o paper.html
    python3 research/resolve_crossref.py paper.html
"""
from __future__ import annotations

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


def norm(t: str) -> set[str]:
    t = re.sub(r"[^a-z0-9 ]", " ", t.lower())
    stop = {"a", "an", "the", "of", "for", "and", "on", "in", "to", "with", "at",
            "its", "by", "from"}
    return {w for w in t.split() if w and w not in stop}


def crossref(doi: str):
    url = f"https://api.crossref.org/works/{doi}"
    try:
        out = subprocess.check_output(
            ["curl", "-sS", "--max-time", "45", "-H",
             "User-Agent: t27-reference-audit (mailto:admin@t27.ai)", url],
            text=True, stderr=subprocess.DEVNULL)
        msg = json.loads(out)["message"]
    except Exception:
        return None
    title = (msg.get("title") or [""])[0]
    authors = "; ".join(
        f"{a.get('given','')} {a.get('family','')}".strip()
        for a in (msg.get("author") or [])[:4])
    year = ((msg.get("issued") or {}).get("date-parts") or [[None]])[0][0]
    return title, authors, year


def main() -> int:
    rows = entries(sys.argv[1])
    checked = agree = leads = unresolved = skipped = 0

    for i, e in enumerate(rows, 1):
        if re.search(r"arXiv[:\s]*[0-9]{4}\.[0-9]{4,5}", e, re.I):
            continue                                    # covered by the arXiv pass
        m = re.search(r"DOI[:\s]*(10\.\d{4,9}/[^\s,]+)", e, re.I)
        cited = re.search(r"[“\"']([^”\"']{6,200})[”\"']", e)
        cited_title = cited.group(1).strip().rstrip(",") if cited else ""

        if not m:
            skipped += 1
            print(f"[{i:>2}] no DOI, not machine-checkable — judge by eye")
            print(f"     {e[:150]}")
            print()
            continue

        checked += 1
        got = crossref(m.group(1).rstrip("."))
        time.sleep(0.4)
        if not got:
            unresolved += 1
            print(f"[{i:>2}] DOI {m.group(1)} did not resolve")
            continue
        real_title, real_authors, year = got
        a, b = norm(cited_title), norm(real_title)
        ov = len(a & b) / max(1, len(a | b))
        if ov >= 0.6:
            agree += 1
            continue
        leads += 1
        print(f"[{i:>2}] DOI {m.group(1)}   overlap {ov:.0%}")
        print(f"     cited : {cited_title}")
        print(f"     actual: {real_title}")
        print(f"     authors: {real_authors}  ({year})")
        print()

    print(f"\nentries with a DOI : {checked}")
    print(f"  titles agree     : {agree}")
    print(f"  LEADS            : {leads}")
    print(f"  DOI unresolved   : {unresolved}")
    print(f"entries with neither arXiv id nor DOI: {skipped}")
    print("\nA lead is not a defect. Read both strings before concluding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
