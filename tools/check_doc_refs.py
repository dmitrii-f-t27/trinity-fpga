#!/usr/bin/env python3
"""Does every file a document names actually exist?

Enumerating the pairs that must agree showed all existing gates are code against
code, and that every pair with a document on one side is unguarded. One of them
-- the paper against its measurements -- is now covered. This covers the rest:
a document that names a file, a script or a gate is making a checkable claim
about the tree, and nothing checked it.

Sixteen claims were withdrawn during this work and three gates were added,
renamed or moved. A path in prose does not update itself.
"""
import re, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = sorted(set(list(ROOT.glob("research/**/*.md")) + list(ROOT.glob("*.md"))
                  + list(ROOT.glob("docs/**/*.md"))))

# A path-like token: has a slash and an extension we own, or is a bare script name
PATHY = re.compile(r'`([A-Za-z0-9_./-]+\.(?:py|v|sh|tex|yml|yaml|md|t27|json))`')

fails, checked, refs = [], 0, 0
for d in DOCS:
    try: txt = d.read_text(errors="ignore")
    except Exception: continue
    checked += 1
    for m in PATHY.finditer(txt):
        p = m.group(1); refs += 1
        if p.startswith("http"): continue
        # A temporary path is expected to be gone; naming one is not a broken
        # reference, it is a note about a run that has finished.
        if p.startswith(("/tmp/", "/private/tmp/", "/var/")): continue
        # A document may name a file precisely to record that it is missing --
        # SCRIPT_ROT names tef_mul_wp.v as the module a build script instantiates
        # and nothing defines. Flagging that would be flagging the finding.
        w = txt[max(0, m.start()-160): m.end()+160].lower()
        if any(k in w for k in ("does not exist", "no definition", "nowhere in",
                                "absent from", "which is gone", "not in the tree")):
            continue
        # Sibling repositories are part of this work and a document may name a
        # path in one of them; that is a real reference, not a dangling one.
        SIBLINGS = ["t27", "trinity-s3ai", "claim-audit-lab", "tri-net", "trios-mesh"]
        cands = [ROOT / p, ROOT / "tools" / p, ROOT / "conformance" / p,
                 ROOT.parent / p, d.parent / p] + [ROOT.parent / sib / p for sib in SIBLINGS]
        # a bare filename may live anywhere in the tree
        if "/" not in p:
            if any(ROOT.rglob(p)): continue
            if any(any((ROOT.parent / sib).rglob(p))
                   for sib in ("t27", "trinity-s3ai", "claim-audit-lab", "tri-net")
                   if (ROOT.parent / sib).is_dir()): continue
        if any(c.exists() for c in cands): continue
        fails.append(f"{d.relative_to(ROOT)}: names `{p}`, which does not exist")

# Ratchet: the tree carries historical documents naming files removed long ago.
# Blocking on that debt would make the gate useless; fail only on NEW ones.
import sys as _s
BASE = pathlib.Path(__file__).with_name("doc_refs_baseline.txt")
print(f"documents scanned: {checked}   path references: {refs}")
uniq = sorted(set(fails))
if "--update-baseline" in _s.argv:
    BASE.write_text("\n".join(uniq) + ("\n" if uniq else ""))
    print(f"baseline written: {len(uniq)} known"); _s.exit(0)
known = {l for l in BASE.read_text().splitlines() if l.strip()} if BASE.exists() else set()
new = sorted(set(uniq) - known)
if new:
    print(f"\nFAIL: {len(new)} NEW dangling reference(s)\n")
    for f in new: print(f"  {f}")
    _s.exit(1)
print(f"OK: no new dangling references ({len(known)} known)")
_s.exit(0)
if fails:
    print(f"\nFAIL: {len(fails)} reference(s) to files that are not there\n")
    for f in sorted(set(fails)): print(f"  {f}")
    sys.exit(1)
print("OK: every file named in a document exists")
