#!/usr/bin/env python3
"""Recompute the 40 silicon-sprint packs from the real oracles.

research/audit_fp32_proxy_golden.py showed that these packs' expected values come
from conformance/golden_conformance_vectors.py, a float32 proxy, and that 6,690
of their 11,520 values disagree with the project's own oracles.

This replaces the expected values -- and only those. Everything the silicon flow
depends on is preserved:

  * same filenames
  * same {a, b, op, result} integer schema
  * same (a, b) input pairs, in the same order
  * same `format` / `op` / `count` keys

and the header gains what it never had: the oracle that produced the values, the
width, the family, a specials legend, and a note.

Two of the ten formats -- fp16_e6m9 and fp24_7m16 -- exist nowhere but in the
proxy. They are consistent IEEE-style layouts (1+6+9 = 16, 1+7+16 = 24) so
ieee_ref's generic codec computes them exactly, but they are deliberately NOT
added to ieee_ref.FORMATS: they are not catalog members, they are formats the
silicon sprint happened to test.

`quire` is left named `quire` because the silicon flow looks the file up by name,
but the proxy's quire was `from_fp32(to_fp32(a))` -- a decode/encode round trip
that ignores b. That is what these vectors test, and the note now says so. What
the QUIRE core on silicon actually computes has never been checked against an
accumulator golden.

Usage:  python3 research/regenerate_silicon_packs.py [--write]
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")
VECTORS = os.path.join(CONF, "vectors")
sys.path.insert(0, CONF)

import gf_ref            # noqa: E402
import bf16_ref          # noqa: E402
import ieee_ref          # noqa: E402
import exact_ops         # noqa: E402
import generate_vectors as G   # noqa: E402

NOTE = {
    "add": "exact Fraction decode/add/encode, round-ties-even.",
    "mul": "exact Fraction decode/mul/encode, round-ties-even.",
    "div": "exact Fraction decode/div/encode, round-ties-even "
           "(conformance/exact_ops.py).",
    "sqrt": "exact sqrt by integer bisection on the exact significand "
            "(conformance/exact_ops.py); b is ignored.",
    "quire": "NOT an accumulator: this is encode(decode(a)), the decode/encode "
             "round trip the fp32 proxy called `quire`. b is ignored. The QUIRE "
             "core on silicon has never been checked against an accumulator "
             "golden.",
}

PROVENANCE = (
    "expected values recomputed from the named oracle. They previously came "
    "from conformance/golden_conformance_vectors.py, a float32 proxy: 6,690 of "
    "11,520 disagreed (research/audit_fp32_proxy_golden.py). Inputs and order "
    "are unchanged from the silicon sprint."
)


def resolve():
    out = {}
    for k in ("gf4", "gf8", "gf16", "gf32"):
        out[k] = (gf_ref, gf_ref.FORMATS[k], "gf", "gf_ref.py")
    out["bf16"] = (bf16_ref, bf16_ref.FORMATS["bfloat16"], "bfloat", "bf16_ref.py")
    for key, canon in (("fp32_e8m23", "binary32"),
                       ("binary64", "binary64"),
                       ("fp128_e15m112", "binary128")):
        out[key] = (ieee_ref, ieee_ref.FORMATS[canon], "ieee", "ieee_ref.py")
    out["fp16_e6m9"] = (ieee_ref, ieee_ref.IEEFormat("fp16_e6m9", 6, 9, 31),
                        "ieee", "ieee_ref.py")
    out["fp24_7m16"] = (ieee_ref, ieee_ref.IEEFormat("fp24_7m16", 7, 16, 63),
                        "ieee", "ieee_ref.py")
    return out


def op_fn(mod, op):
    if op == "add":
        return getattr(mod, "gf_add", None) or mod.format_add
    if op == "mul":
        return getattr(mod, "gf_mul", None) or mod.format_mul
    if op == "div":
        return exact_ops.make_div(mod)
    if op == "sqrt":
        return exact_ops.make_sqrt(mod)
    if op == "quire":
        return lambda f, a, b: mod.encode(f, mod.decode(f, a))
    raise KeyError(op)


def main():
    write = "--write" in sys.argv
    res = resolve()
    changed = total = raised_total = 0
    files = 0
    for fn in sorted(os.listdir(VECTORS)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(VECTORS, fn)
        doc = json.load(open(path))
        if "oracle" in doc:
            continue
        key, op = doc["format"], doc["op"]
        mod, fmt, family, oracle_file = res[key]
        mask = G.get_mask(fmt)
        width = G.get_width(fmt)
        fn_op = op_fn(mod, op)

        out = []
        diff = raised = 0
        for v in doc["vectors"]:
            a, b = v["a"], v["b"]
            try:
                got = fn_op(fmt, a & mask, b & mask) & mask
            except Exception:                     # noqa: BLE001
                raised += 1
                got = v["result"]                 # leave untouched, report it
            if got != v["result"]:
                diff += 1
            out.append({"a": a, "b": b, "op": op, "result": got})

        new = {
            "format": key,
            "op": op,
            "oracle": oracle_file,
            "family": family,
            "width": width,
            "specials": G.specials_legend(fmt, family, width),
            "note": NOTE[op],
            "provenance": PROVENANCE,
            "count": len(out),
            "vectors": out,
        }
        files += 1
        changed += diff
        total += len(out)
        raised_total += raised
        print("%-30s %-12s %-6s  corrected %4d/%-4d%s"
              % (fn, key, op, diff, len(out),
                 ("  RAISED %d" % raised) if raised else ""))
        if write:
            with open(path, "w") as fh:
                json.dump(new, fh, indent=2)
                fh.write("\n")

    print()
    print("packs            : %d" % files)
    print("vectors          : %d" % total)
    print("values corrected : %d (%.1f%%)" % (changed, 100.0 * changed / max(1, total)))
    print("oracle raised on : %d (left as-is)" % raised_total)
    print("written" if write else "dry run -- pass --write to apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
