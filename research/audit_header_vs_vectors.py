#!/usr/bin/env python3
"""Does a pack's header describe the vectors that are actually in it?

Pass 231 checked the specials legend -- the part of the header that names codes.
This checks the rest of it: the operation, the oracle, the width, the family.

The important difference from research/audit_pack_reproducibility.py: that audit
rebuilds a pack by asking generate_vectors to make it again, and generate_vectors
decides which oracle and which function to use from its own MODULES table. If the
table said "add" and handed over the multiply function, the rebuild would match
and the audit would pass. This one reads the oracle name and the operation name
OUT OF THE PACK ITSELF, resolves them, and recomputes every vector. It is driven
by the claim, not by the thing that made the claim.

It also covers the 40 packs generate_vectors cannot rebuild at all -- those have
never had their expected values recomputed by anything.

Checks
  1. operation + oracle : recompute every vector from the named oracle
  2. width              : header width vs the oracle's own width for that format
  3. family             : header family vs the family the oracle belongs to
  4. attribution        : does the pack name an oracle at all
  5. shared inputs      : add/mul/sub packs for one format must use the same pairs
  6. duplicates         : a repeated (a, b) pair is a vector that buys nothing

Usage:  python3 research/audit_header_vs_vectors.py
"""
import collections
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")
VECTORS = os.path.join(CONF, "vectors")

sys.path.insert(0, CONF)
import generate_vectors as G  # noqa: E402  (helpers: get_width, get_mask, make_sub_fn)
import exact_ops              # noqa: E402
import ieee_ref               # noqa: E402

FAMILY_OF_ORACLE = {m + ".py": fam for m, _a, _m, fam in G.MODULES}

# Two formats exist only in the silicon-sprint packs. Both are consistent
# IEEE-style layouts (1+6+9 = 16, 1+7+16 = 24) so ieee_ref's generic codec
# computes them, but they are not catalog members and are deliberately absent
# from ieee_ref.FORMATS. See research/regenerate_silicon_packs.py.
SPRINT_ONLY = {
    "fp16_e6m9": ieee_ref.IEEFormat("fp16_e6m9", 6, 9, 31),
    "fp24_7m16": ieee_ref.IEEFormat("fp24_7m16", 7, 16, 63),
}

# The silicon-sprint packs name a format the oracle spells differently.
ALIAS = {"bf16": "bfloat16", "fp32_e8m23": "binary32",
         "fp128_e15m112": "binary128"}


def op_functions(mod):
    """Find this module's add and mul without consulting the MODULES table.

    Every oracle exposes them as `format_add`/`format_mul` or as
    `<prefix>_add`/`<prefix>_mul` (gf_ref, tekum_ref). Discover by suffix and
    prefer the generic name when a module happens to have both.
    """
    found = {"add": [], "mul": []}
    for name in dir(mod):
        for op in ("add", "mul"):
            if name.endswith("_" + op) and callable(getattr(mod, name, None)):
                found[op].append(name)
    out = {}
    for op, names in found.items():
        if not names:
            out[op] = None
        elif "format_" + op in names:
            out[op] = getattr(mod, "format_" + op)
        elif len(names) == 1:
            out[op] = getattr(mod, names[0])
        else:
            out[op] = None  # ambiguous -- report rather than guess
    return out


def own_format(mod, key):
    fmts = getattr(mod, "FORMATS", {})
    f = fmts.get(key)
    if f is None and key in ALIAS:
        f = fmts.get(ALIAS[key])
    if f is None:
        f = SPRINT_ONLY.get(key)
    return f


def find_owner(key, modules):
    owners = [name for name, mod in modules.items() if own_format(mod, key) is not None]
    return owners


def main():
    packs = sorted(f for f in os.listdir(VECTORS) if f.endswith(".json"))
    if not packs:
        print("no packs")
        return 1

    modules = {}
    for mod_name, _a, _m, _f in G.MODULES:
        modules[mod_name + ".py"] = importlib.import_module(mod_name)

    bad_value = []       # recomputation disagreed
    bad_width = []
    bad_family = []
    unattributed = []
    unresolvable = []
    dupes = []
    checked = 0
    vectors_checked = 0
    inputs_by_format = collections.defaultdict(dict)   # fmt -> op -> tuple of pairs

    for fn in packs:
        path = os.path.join(VECTORS, fn)
        doc = json.load(open(path))
        key = doc["format"]
        op = doc.get("operation") or doc.get("op")
        oracle = doc.get("oracle")

        # `gf_ref.py + exact_ops.py` means: that oracle's decode/encode, with
        # div and sqrt built on top by exact_ops. Resolve to the primary.
        helper_exact = False
        if oracle and " + " in oracle:
            parts = [p.strip() for p in oracle.split("+")]
            helper_exact = "exact_ops.py" in parts
            oracle = parts[0]

        if oracle is None:
            owners = find_owner(key, modules)
            unattributed.append((fn, key, op, owners))
            if len(owners) != 1:
                unresolvable.append((fn, key, owners))
                continue
            oracle = owners[0]
            declared_oracle = None
        else:
            declared_oracle = oracle

        mod = modules.get(oracle)
        if mod is None:
            unresolvable.append((fn, key, ["named oracle %s not in MODULES" % oracle]))
            continue
        fmt = own_format(mod, key)
        if fmt is None:
            unresolvable.append((fn, key, ["%s has no format %r" % (oracle, key)]))
            continue

        fns = op_functions(mod)
        if op == "sub":
            base = fns["add"]
            fn_op = G.make_sub_fn(base, mod, FAMILY_OF_ORACLE[oracle]) if base else None
        elif op == "div":
            fn_op = exact_ops.make_div(mod)
        elif op == "sqrt":
            fn_op = exact_ops.make_sqrt(mod)
        elif op == "quire":
            # the silicon-sprint "quire" is encode(decode(a)); b is ignored
            fn_op = lambda f, a, b, _m=mod: _m.encode(f, _m.decode(f, a))
        else:
            fn_op = fns.get(op)
        if fn_op is None:
            unresolvable.append((fn, key, ["no %s function on %s" % (op, oracle)]))
            continue

        width = G.get_width(fmt)
        mask = G.get_mask(fmt)

        # 2/3: header width and family vs the oracle
        if declared_oracle is not None:
            if doc.get("width") != width:
                bad_width.append((fn, doc.get("width"), width))
            fam = FAMILY_OF_ORACLE[oracle]
            # A pack built by `<oracle> + exact_ops.py` may call its family
            # "exact" -- that names the construction, not the format family.
            if doc.get("family") not in (fam, "exact" if helper_exact else fam):
                bad_family.append((fn, doc.get("family"), fam))

        # 1: recompute
        mism = 0
        first = None
        seen = set()
        dup = 0
        pairs = []
        for v in doc["vectors"]:
            if "expected" in v:
                a = int(v["a"], 16)
                b = int(v["b"], 16)
                exp = int(v["expected"], 16)
            else:
                a, b, exp = v["a"], v["b"], v["result"]
            pairs.append((a, b))
            if (a, b) in seen:
                dup += 1
            seen.add((a, b))
            try:
                got = fn_op(fmt, a, b) & mask
            except Exception as e:                    # noqa: BLE001
                got = "raised %s" % type(e).__name__
            vectors_checked += 1
            if got != exp:
                mism += 1
                if first is None:
                    first = (v, got)
        if mism:
            bad_value.append((fn, oracle, op, mism, len(doc["vectors"]), first))
        if dup:
            dupes.append((fn, dup, len(doc["vectors"])))
        inputs_by_format[key][op] = tuple(pairs)
        checked += 1

    # 5: generate_vectors documents that add, mul and sub for one format exercise
    # the SAME (a, b) pairs -- the seed is independent of the operation. That
    # invariant is ITS invariant, so only its own packs are eligible: div, sqrt
    # and quire come from other generators that sample differently, and comparing
    # across them would be comparing two unrelated designs.
    #
    # A pack can still be shorter than its siblings, because build_document
    # silently drops any pair the oracle raised on. So the test is SUBSET, and a
    # proper subset means vectors were dropped with no record of how many or why.
    SHARED_SEED_OPS = ("add", "mul", "sub")
    input_drift = []
    dropped = []
    for key, byop in inputs_by_format.items():
        eligible = {op: p for op, p in byop.items() if op in SHARED_SEED_OPS}
        if len(eligible) < 2:
            continue
        ref_op, ref = max(eligible.items(), key=lambda kv: len(kv[1]))
        ref_set = set(ref)
        for op, pairs in sorted(eligible.items()):
            if op == ref_op:
                continue
            extra = set(pairs) - ref_set
            if extra:
                input_drift.append((key, ref_op, op, len(ref), len(pairs)))
            elif len(pairs) < len(ref):
                dropped.append((key, ref_op, op, len(ref) - len(pairs), len(ref)))

    print("packs on disk                         : %d" % len(packs))
    print("packs recomputed from their own header: %d" % checked)
    print("vectors recomputed                    : %d" % vectors_checked)
    print()
    print("value disagreements (pack vs oracle)  : %d" % len(bad_value))
    for fn, oracle, op, m, n, first in bad_value[:12]:
        print("   %-34s %s %s  %d/%d  first=%s got=%s"
              % (fn, oracle, op, m, n, first[0], first[1]))
    print("header width  != oracle width         : %d" % len(bad_width))
    for row in bad_width[:12]:
        print("   %-34s header=%s oracle=%s" % row)
    print("header family != oracle family        : %d" % len(bad_family))
    for row in bad_family[:12]:
        print("   %-34s header=%s oracle=%s" % row)
    print("packs naming NO oracle                : %d" % len(unattributed))
    for fn, key, op, owners in unattributed[:6]:
        print("   %-34s format=%-10s op=%-4s resolved-> %s" % (fn, key, op, owners))
    if len(unattributed) > 6:
        print("   ... and %d more" % (len(unattributed) - 6))
    print("packs that could not be resolved      : %d" % len(unresolvable))
    for fn, key, why in unresolvable[:12]:
        print("   %-34s %s %s" % (fn, key, why))
    print("packs with duplicate (a,b) pairs      : %d" % len(dupes))
    for row in dupes[:8]:
        print("   %-34s %d dup of %d" % row)
    print("formats whose ops use DIFFERENT inputs: %d" % len(input_drift))
    for row in input_drift[:12]:
        print("   %-12s %s vs %s : %d vs %d pairs" % row)
    print("packs silently short of the full pair set: %d" % len(dropped))
    for row in dropped[:12]:
        print("   %-12s %s vs %s : %d of %d pairs dropped (oracle raised)" % row)

    bad = (len(bad_value) + len(bad_width) + len(bad_family)
           + len(unresolvable) + len(input_drift))
    print()
    print("VERDICT: %s" % ("CLEAN" if bad == 0 else "%d problems" % bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
