#!/usr/bin/env python3
"""Audit the candidate packs generated in pass 11 against knowledge acquired after.

The twelve packs in conformance/vectors_generated/ were derived before passes
14-15 established that the takum oracle mis-handles the negative half of its code
space. A pack derived from an oracle inherits that oracle's defects, so the packs
must be re-examined before anyone treats them as publishable.

This audits the PACK DATA itself — not the oracle — so it stays valid even if the
oracle is later fixed:

  NEGATION   check decode((-raw) mod 2^n) == -decode(raw)
             and decode(raw XOR msb) == -decode(raw); report which rule the pack's
             values actually obey. A tapered format that obeys XOR rather than
             two's complement carries the takum-class defect.
  MONOTONIC  within the positive half.
  ZERO       the pack should contain a zero-valued code.

Curated packs are auditable too once the generator emits complement witnesses
(added after this audit first found the rule untestable). A rule is judged only
where its witness is present; a missing complement means "not covered", never
"violated".

Run:  python3 research/audit_generated_packs.py
Exit: 0 if no pack shows the takum-class signature, 1 otherwise.
"""
from __future__ import annotations
import glob
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(REPO, "conformance", "vectors_generated")

# Formats in the takum/tapered lineage, where two's-complement negation is
# expected. Anything here obeying XOR instead carries the pass-14/15 signature.
TAPERED = ("takum", "tekum", "posit")


def audit(path):
    with open(path) as fh:
        pack = json.load(fh)
    name = pack["format_name"]
    width = pack["catalog"]["bits"]
    mode = pack["vector_mode"]
    span = 1 << width
    msb = span >> 1

    vals = {}
    for v in pack["vectors"]:
        raw = v.get(f"{name}_bits_int")
        if raw is None:
            continue
        vals[raw] = v.get("decoded_f64")   # None for specials

    res = {"name": name, "width": width, "mode": mode,
           "n": len(vals), "has_zero": any(x == 0.0 for x in vals.values() if x is not None)}

    # Curated packs can now attest to negation too, provided the generator
    # included complement witnesses (added after the pass-21 audit found that
    # corners alone made the rule untestable).

    xor_ok = twos_ok = True
    tested = 0
    for raw, a in vals.items():
        if a is None or raw in (0, msb):
            continue
        bx = vals.get(raw ^ msb)
        bt = vals.get((-raw) % span)
        if bx is None and bt is None:
            continue
        tested += 1
        # Judge a rule ONLY where its witness is present. A missing complement
        # means "not covered by this pack", not "rule violated" -- conflating the
        # two made well-formed curated packs report `neither`.
        if bx is not None and bx != -a:
            xor_ok = False
        if bt is not None and bt != -a:
            twos_ok = False
    res["negation"] = ("xor" if xor_ok else "twos" if twos_ok else "neither") \
        if tested else "untestable"
    res["tested"] = tested

    prev = None
    breaks = 0
    for raw in sorted(r for r in vals if r < msb):
        a = vals[raw]
        if a is None:
            continue
        if prev is not None and a <= prev:
            breaks += 1
        prev = a
    res["monotonic_breaks"] = breaks
    return res


def main() -> int:
    paths = sorted(glob.glob(os.path.join(GEN, "*.json")))
    if not paths:
        print(f"no generated packs found in {GEN}")
        return 0

    print(f"{'pack':<14}{'bits':>5} {'mode':<15}{'vectors':>8}  "
          f"{'negation':<11}{'mono breaks':>12}  zero")
    print("-" * 74)

    suspect = []
    for p in paths:
        r = audit(p)
        mb = r.get("monotonic_breaks", "-")
        print(f"{r['name']:<14}{r['width']:>5} {r['mode']:<15}{r['n']:>8}  "
              f"{r['negation']:<11}{str(mb):>12}  {'yes' if r['has_zero'] else 'NO'}")
        if any(r["name"].startswith(t) for t in TAPERED) and r["negation"] == "xor":
            suspect.append(r["name"])

    print()
    if suspect:
        print(f"TAKUM-CLASS SIGNATURE in {len(suspect)} pack(s): {', '.join(suspect)}")
        print("A tapered format obeying XOR negation instead of two's complement")
        print("matches the defect established in specs/numeric/negation_invariant.t27.")
        print("These packs inherit it from their oracle and must not be published")
        print("until the oracle question is settled with the format author.")
    else:
        print("No pack shows the takum-class negation signature.")
    return 1 if suspect else 0


if __name__ == "__main__":
    raise SystemExit(main())
