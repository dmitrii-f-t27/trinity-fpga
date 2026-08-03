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
Exit: 0. The XOR-negation signature is reported, not failed on -- see the
note printed with it. Pass 162 found this audit blocking three packs on a
finding its own cited spec retracted eleven passes earlier.
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
    # The published corpus is not schema-uniform: some packs omit format_name,
    # some omit vector_mode, and the bit-width key varies. Derive defensively and
    # record what was missing rather than crashing on the variation.
    base = os.path.basename(path).replace("_conformance_v0.json", "")
    name = pack.get("format_name") or pack.get("format", base).lower()
    cat = pack.get("catalog") or {}
    width = cat.get("bits") or cat.get("width") or 0
    if not width:
        digits = "".join(c for c in base if c.isdigit())
        width = int(digits) if digits else 0
    mode = pack.get("vector_mode") or "(unstated)"
    span = 1 << width
    msb = span >> 1

    from fractions import Fraction as _F
    vals = {}
    for v in pack.get("vectors", []):
        raw = v.get(f"{name}_bits_int")
        if raw is None:                     # key naming also varies
            for k in v:
                if k.endswith("_bits_int"):
                    raw = v[k]
                    break
        # Layout B (wide GF formats): code in `bits`, value as a DECIMAL STRING in
        # `value`. That is not arbitrary drift -- a gf1024 value has a 632-bit
        # mantissa and cannot be held in binary64 at all, so decoded_f64 would be
        # lossy or impossible. Read it exactly, as a Fraction.
        if raw is None and isinstance(v.get("bits"), int):
            raw = v["bits"]
            sv = v.get("value")
            if isinstance(sv, str) and v.get("value_encoding") == "decimal":
                try:
                    vals[raw] = _F(sv)
                except Exception:
                    vals[raw] = None
            else:
                vals[raw] = None
            continue
        if raw is None:
            continue
        d = v.get("decoded_f64")
        # decoded_f64 is sometimes serialised as a string ("NaN", "Infinity", or
        # a quoted number). Coerce; anything non-numeric is treated as a special.
        if isinstance(d, str):
            try:
                d = float(d)
            except ValueError:
                d = None
        if isinstance(d, float) and (d != d or abs(d) == float("inf")):
            d = None
        vals[raw] = d

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
    # Optional directory argument so the same audit can be run against the
    # PUBLISHED catalog packs, not just the locally generated candidates.
    target = sys.argv[1] if len(sys.argv) > 1 else GEN
    paths = sorted(glob.glob(os.path.join(target, "*.json")))
    if not paths:
        print(f"no packs found in {target}")
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
        print(f"XOR-NEGATION ORACLE in {len(suspect)} pack(s): "
              f"{', '.join(suspect)}")
        print("These use a sign-and-magnitude oracle, which negates by XOR rather")
        print("than by two's complement. That is DOCUMENTED and is not a defect.")
        print()
        print("specs/numeric/negation_invariant.t27 opens by retracting exactly this")
        print("reading, on 2026-07-31, and names conformance/tekum_ref.py as carrying")
        print("the same deliberate choice: exact-Fraction arithmetic cannot represent")
        print("logarithmic values, so the oracle implements a linear structural model")
        print("and says so in its own header.")
        print()
        print("This audit cited that spec as establishing a defect and blocked three")
        print("packs from publication on it, for a claim the spec had already")
        print("withdrawn. The block is lifted. What remains open is the separate")
        print("question of which variant the project means -- recorded in")
        print("specs/numeric/takum_variant_split.t27, owned by the author, and not")
        print("something a pack audit decides.")
    else:
        print("No pack uses a sign-and-magnitude oracle.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
