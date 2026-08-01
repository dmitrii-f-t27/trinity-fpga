#!/usr/bin/env python3
"""Emit ready-to-paste LaTeX bibitems for every reference found defective.

Passes 74-75 resolved both bibliographies mechanically and found more defects than
the hand audit had. This turns that list into text an author can paste, with the
authoritative metadata fetched fresh rather than transcribed from a report.

Full author lists come from the arXiv API in one batched request -- the audit
scripts truncate to four names for display, which is not good enough for a
bibliography.

    python3 research/build_corrected_bibitems.py
"""
from __future__ import annotations

import re
import subprocess

# arXiv id -> (paper, ref number, what the paper currently claims)
DEFECTS = {
    "2606.05017": ("B", "[1]", "GoldenFloat: A phi-anchored numeric format family "
                               "and the identity phi^2+1/phi^2=3"),
    "2412.20273": ("B", "[2]", "Takum arithmetic: A new paradigm for low-precision "
                               "numerics"),
    "2511.12294": ("B", "[3]", "ProofWright: Towards verified floating-point "
                               "arithmetic"),
    "2602.15965": ("B", "[4]", "P3109 FLoPS: A Lean 4 formalization of IEEE P3109 "
                               "floating-point semantics"),
    "2601.19213": ("B", "[8]", "M2XFP: A unified mixed-precision microscaling "
                               "floating-point representation"),
    "2504.07835": ("B", "[10]", "Pychop: Emulating low-precision arithmetic in "
                                "Python for ML and scientific computing"),
    "2412.20268": ("B", "[13]", "Takum arithmetic in sparse iterative solvers: "
                                "A precision-vs-storage study"),
    "2606.04028": ("B", "[19]", "(no title given)"),
    "2601.19026": ("B", "[20]", "(no title given)"),
}

KEYS = {
    "2606.05017": "goldenfloat2026", "2412.20273": "hunhold2024integer",
    "2511.12294": "proofwright2025", "2602.15965": "flops2026",
    "2601.19213": "m2xfp2026", "2504.07835": "pychop2025",
    "2412.20268": "hunhold2024solvers", "2606.04028": "sarnoff2026p3109",
    "2601.19026": "fasoli2026finer",
}


def fetch(ids):
    url = ("https://export.arxiv.org/api/query?max_results=100&id_list="
           + ",".join(ids))
    out = subprocess.check_output(["curl", "-sS", "--max-time", "90", url],
                                  text=True)
    found = {}
    for chunk in out.split("<entry>")[1:]:
        idm = re.search(r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5})", chunk)
        if not idm:
            continue
        title = re.search(r"<title>(.*?)</title>", chunk, re.S)
        names = re.findall(r"<name>(.*?)</name>", chunk, re.S)
        pub = re.search(r"<published>(\d{4})", chunk)
        found[idm.group(1)] = (
            " ".join(title.group(1).split()) if title else "",
            [n.strip() for n in names],
            pub.group(1) if pub else "")
    return found


def latex_authors(names):
    """Surname-initial form, as the existing bibliography uses."""
    out = []
    for n in names:
        parts = n.split()
        if len(parts) < 2:
            out.append(n)
            continue
        initials = " ".join(p[0] + "." for p in parts[:-1])
        out.append(f"{initials} {parts[-1]}")
    if len(out) == 1:
        return out[0]
    if len(out) == 2:
        return " and ".join(out)
    return ", ".join(out[:-1]) + ", and " + out[-1]


def main() -> int:
    meta = fetch(list(DEFECTS))
    print("% Corrected bibitems -- titles and authors fetched from the arXiv API,")
    print("% not transcribed. Verify against the rendered PDF before submitting.\n")

    for aid, (paper, ref, claimed) in DEFECTS.items():
        got = meta.get(aid)
        if not got:
            print(f"% {paper} {ref}: arXiv:{aid} did not resolve -- check by hand\n")
            continue
        title, names, year = got
        print(f"% Paper {paper}, ref {ref}")
        print(f"%   currently: {claimed}")
        print(f"\\bibitem{{{KEYS[aid]}}} {latex_authors(names)}, ``{title},''")
        print(f"  \\texttt{{arXiv:{aid}}}, {year}.\n")

    print("""
% ---------------------------------------------------------------------------
% Not fetchable from arXiv; corrected by hand from the authoritative source:
%
% Paper B [12]  -- author initial is wrong
\\bibitem{libtakum} L. Hunhold, ``libtakum: A reference C library for takum
  arithmetic,'' \\url{https://github.com/takum-arithmetic/libtakum}, 2024--2025.
%   currently: "C. Hunhold". The author is Laslo Hunhold (arXiv:2404.18603).
%
% Paper B [18]  -- the document carries no version number
\\bibitem{p3109interim} IEEE P3109 Working Group, ``IEEE P3109 Interim Report,''
  IEEE Standards Association, retrieved 2026-08-01.
  \\url{https://github.com/P3109/Public}.
%   currently: "IEEE SA P3109 Interim Report v3.2.0". No version string appears
%   anywhere in that document; cite it by retrieval date.
%
% Paper A [11]  -- the DOI resolves to a DIFFERENT work, already cited as [10].
%   Delete [11] as a duplicate, and if the ARITH 2025 hardware-evaluation paper
%   was intended, add it under its own DOI -- 10.1109/ARITH64983.2025.00019
%   resolves to "Evaluation of Bfloat16, Posit, and Takum Arithmetics in Sparse
%   Linear Solvers" (Hunhold and Quinlan), which is what [10] already cites.
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
