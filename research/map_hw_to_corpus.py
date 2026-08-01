#!/usr/bin/env python3
"""How many of the 83 conformance packs have hardware confirmation?

Two lines of this campaign have run separately: the 83-pack software corpus, and the
Tier-E hardware matrix in trinity-fpga#199 where 34 cells carry a complete four-link
evidence chain (pass 91).

Nobody has crossed them. "83 formats, bit-exact" and "34 cells verified on silicon"
are different claims about overlapping sets, and the first question a reader asks is
which formats have which.

    python3 research/map_hw_to_corpus.py
"""
from __future__ import annotations

import json
import re
import subprocess

LINKS = {
    "ci": re.compile(r"github\.com/[^\s)]*/(?:actions/runs|runs)/\d+", re.I),
    "sha": re.compile(r"\b[0-9a-f]{64}\b", re.I),
    "uart": re.compile(r"HW RESULT:\s*(\d+)/(\d+)\s*bit-exact", re.I),
    "idcode": re.compile(r"0x13636093", re.I),
}

CELL = re.compile(r"\b(gf\d+|gfternary|bcd|binary\d+|decimal\d+|fp8_e\dm\d|fp8|"
                  r"fp6_e\dm\d|fp4_e\dm\d|bfloat\d+|mxfp\d+|mxgf\d+|posit\d+|"
                  r"takum\d+|tekum\d+|afp|cray_float|vax_[dfgh]|ms_mbf\d+|"
                  r"ibm_hfp\d+|int\d+|uint\d+|lns\d+|nf4|pdp11_float|"
                  r"x87_\w+|double_double|quad_double)\b", re.I)


def hw_cells():
    """Format ids whose Tier-E chain is complete, with the reported result."""
    found = {}
    for page in range(1, 6):
        raw = subprocess.run(
            ["gh", "api", "repos/gHashTag/trinity-fpga/issues/199/comments"
             f"?per_page=100&page={page}"], capture_output=True, text=True).stdout
        try:
            chunk = json.loads(raw)
        except json.JSONDecodeError:
            break
        if not chunk:
            break
        for c in chunk:
            body = c.get("body") or ""
            if not all(p.search(body) for p in LINKS.values()):
                continue
            m = LINKS["uart"].search(body)
            res = f"{m.group(1)}/{m.group(2)}" if m else "?"
            for cell in {x.lower() for x in CELL.findall(body)}:
                found.setdefault(cell, res)
    return found


def corpus_ids():
    raw = subprocess.run(
        ["gh", "api", "repos/gHashTag/t27/contents/conformance/vectors/"
         "INDEX_all_formats.json", "--jq", ".content"],
        capture_output=True, text=True).stdout
    import base64
    idx = json.loads(base64.b64decode(raw))
    return {e["id"]: e.get("kind", "?") for e in idx["packs"]}


def main() -> int:
    hw = hw_cells()
    packs = corpus_ids()
    print(f"Tier-E cells with a complete chain : {len(hw)}")
    print(f"packs in the corpus                : {len(packs)}\n")

    both = {k: (packs[k], hw[k]) for k in packs if k in hw}
    sw_only = sorted(k for k in packs if k not in hw)
    hw_not_in_corpus = sorted(k for k in hw if k not in packs)

    print(f"packs WITH hardware confirmation : {len(both)}")
    for k, (kind, res) in sorted(both.items()):
        print(f"    {k:<14} {kind:<10} {res}")

    print(f"\npacks with SOFTWARE evidence only : {len(sw_only)}")
    print("    " + ", ".join(sw_only))

    if hw_not_in_corpus:
        print(f"\nTier-E cells not matching a pack id : {len(hw_not_in_corpus)}")
        print("    " + ", ".join(hw_not_in_corpus))
        print("    (naming differences, or hardware cells with no published pack)")

    pct = 100 * len(both) / max(1, len(packs))
    print(f"\n{len(both)} of {len(packs)} packs ({pct:.0f}%) carry hardware evidence.")
    print("""
The remainder are not unverified -- they carry the software conformance the corpus
is built on. What they lack is a physical-board result, which is a different and
stronger claim, and the distinction is worth stating wherever both appear.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
