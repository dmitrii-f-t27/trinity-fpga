#!/usr/bin/env python3
"""Which \\cite keys in the submission resolve to nothing?

Item 9 of research/CORRECTIONS_PACKAGE_both_preprints.md reports three keys that
render as [?] in the built PDF. That is the one item in the package that is a
submission defect rather than a claim about the work, and it was the last one with
no tool behind it -- established by reading the PDF.

A key with no entry is mechanically detectable from the source, and the source is
in the repository: research/arxiv_submission/paper.tex and paper.bib.

WHAT COUNTS AS DEFINED
----------------------
A @entry{key, in the .bib, or a \\bibitem{key} in the .tex. Both, because a paper
can carry a manual thebibliography and a .bib at once, and checking only one would
report keys as missing that resolve perfectly well.

The reverse direction is checked too. An entry defined and never cited is not a
defect -- it costs nothing in the PDF -- but a bibliography that has drifted far
from the text is worth seeing.

WHAT THIS CANNOT DO
-------------------
Say what a missing key SHOULD point to. Two of the three name external work --
UFP4 and QuEST -- and resolving them needs the publications, which is the same
thing blocked for the competitor-figure check. This script reports the key, the
line and the sentence around it, and stops there. Inventing a plausible-looking
bibliography entry for a paper nobody has read would be a worse defect than the
missing entry.

Usage:  python3 research/audit_cite_keys.py [path/to/paper.tex]

Exits non-zero if any cited key is undefined.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, "arxiv_submission", "paper.tex")

CITE = re.compile(r"\\cite[tpa]?\*?(?:\[[^\]]*\])*\{([^}]*)\}")
BIBENTRY = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,")
BIBITEM = re.compile(r"\\bibitem(?:\[[^\]]*\])?\{([^}]*)\}")


def read(path):
    return io.open(path, encoding="utf-8", errors="replace").read()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    tex = args[0] if args else DEFAULT
    if not os.path.exists(tex):
        print("no such file: %s" % tex)
        print("Pass the path to the submission .tex. Exiting 2 rather than")
        print("reporting a clean scan of nothing.")
        return 2
    src = read(tex)
    bib_path = os.path.splitext(tex)[0] + ".bib"
    bib = read(bib_path) if os.path.exists(bib_path) else ""

    cited = {}
    for m in CITE.finditer(src):
        for k in m.group(1).split(","):
            k = k.strip()
            if k:
                cited.setdefault(k, src.count("\n", 0, m.start()) + 1)

    defined = set(m.group(1).strip() for m in BIBENTRY.finditer(bib))
    defined |= set(m.group(1).strip() for m in BIBITEM.finditer(src))

    print("source        : %s" % os.path.relpath(tex, os.path.dirname(HERE)))
    print("bibliography  : %s"
          % (os.path.basename(bib_path) if bib else "none found alongside"))
    print("keys cited    : %d" % len(cited))
    print("keys defined  : %d" % len(defined))
    print()

    missing = sorted(k for k in cited if k not in defined)
    print("CITED BUT NOT DEFINED -- these render as [?] : %d" % len(missing))
    lines = src.splitlines()
    for k in missing:
        ln = cited[k]
        print()
        print("    %-16s line %d" % (k, ln))
        for i in range(max(0, ln - 2), min(len(lines), ln + 1)):
            print("        %s" % lines[i].strip()[:96])

    unused = sorted(defined - set(cited))
    print()
    print("defined but never cited (harmless, shown for drift) : %d" % len(unused))
    for k in unused[:10]:
        print("    %s" % k)
    if len(unused) > 10:
        print("    ... and %d more" % (len(unused) - 10))

    print()
    if missing:
        print("This says which keys are missing, not what they should point to.")
        print("Inventing a plausible bibliography entry for a paper nobody has read")
        print("would be a worse defect than the missing entry.")
    else:
        print("every cited key resolves.")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
