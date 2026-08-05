#!/usr/bin/env python3
"""How much of the "golden" in the 40 fp32-proxy packs is actually golden?

conformance/vectors holds two populations. 285 packs name the oracle that made
them and carry a specials legend. The other 40 name nothing. They come from
conformance/golden_conformance_vectors.py -- proved by regenerating all 40 and
getting byte-identical output -- which computes every expected value by decoding
the operand into a **Python float32**, doing the operation in float32, and
encoding the result back.

That is fine for a 16-bit format with a 7-bit mantissa. It is not fine for
binary64 (52-bit mantissa) or fp128_e15m112 (112-bit), and the decoder has
several behaviours that are wrong for every format:

  * subnormals decode with the mantissa ZEROED (`if exp == 0: fp32_mant = 0`),
    so all subnormals of a format collapse to the single value 2**(1-bias)
  * NaN encodes to +0 (`if f != f: return 0`)
  * underflow flushes to signed zero -- the encoder can never emit a subnormal
  * x/0 returns sign=1, exp=all-ones, mant=0 -- NEGATIVE infinity, for every a,
    including 0/0 (which should be NaN) and a>0 (which should be +Inf)
  * sqrt of a negative returns 0, not NaN
  * "quire" is `from_fp32(to_fp32(a))` -- a decode/encode round trip that
    ignores b entirely. It is not an accumulator.

And the GF layouts disagree with gf_ref, the oracle that matches silicon:

    format   proxy (E,M,bias)   gf_ref (E,M,bias)   1+E+M
    gf4      (2, 2, 1)          (1, 2, 0)           proxy 5 bits in a 4-bit format
    gf8      (3, 4, 3)          (3, 4, 3)           agrees
    gf16     (5, 10, 15)        (6, 9, 31)          different split, same width
    gf32     (7, 25, 63)        (12, 19, 2047)      proxy 33 bits in a 32-bit format

This recomputes every one of those vectors from the real oracle for that format
and counts the disagreements, per pack and per cause.

Usage:  python3 research/audit_fp32_proxy_golden.py
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

# proxy format key -> (oracle module, format object)
def resolve():
    out = {}
    for k in ("gf4", "gf8", "gf16", "gf32"):
        out[k] = (gf_ref, gf_ref.FORMATS[k])
    out["bf16"] = (bf16_ref, bf16_ref.FORMATS["bfloat16"])
    out["fp32_e8m23"] = (ieee_ref, ieee_ref.FORMATS["binary32"])
    out["binary64"] = (ieee_ref, ieee_ref.FORMATS["binary64"])
    out["fp128_e15m112"] = (ieee_ref, ieee_ref.FORMATS["binary128"])
    # No oracle ships these two, but both are consistent IEEE-style layouts
    # (1 + 6 + 9 = 16, 1 + 7 + 16 = 24), so ieee_ref's generic codec covers them.
    out["fp16_e6m9"] = (ieee_ref, ieee_ref.IEEFormat("fp16_e6m9", 6, 9, 31))
    out["fp24_7m16"] = (ieee_ref, ieee_ref.IEEFormat("fp24_7m16", 7, 16, 63))
    return out


def op_fn(mod, fmt, op):
    if op == "add":
        return getattr(mod, "gf_add", None) or mod.format_add
    if op == "mul":
        return getattr(mod, "gf_mul", None) or mod.format_mul
    if op == "div":
        return exact_ops.make_div(mod)
    if op == "sqrt":
        return lambda f, a, b: exact_ops.make_sqrt(mod)(f, a, b)
    if op == "quire":
        # the proxy's "quire" is decode-then-encode; hold it to that claim
        return lambda f, a, b: mod.encode(f, mod.decode(f, a))
    raise KeyError(op)


def main():
    res = resolve()
    packs = sorted(f for f in os.listdir(VECTORS) if f.endswith(".json"))
    rows = []
    tot_v = tot_bad = 0
    for fn in packs:
        doc = json.load(open(os.path.join(VECTORS, fn)))
        if "oracle" in doc:
            continue
        key, op = doc["format"], doc["op"]
        mod, fmt = res[key]
        mask = G.get_mask(fmt)
        width = G.get_width(fmt)
        fn_op = op_fn(mod, fmt, op)
        bad = raised = 0
        first = None
        for v in doc["vectors"]:
            a, b, exp = v["a"], v["b"], v["result"]
            if a > mask or b > mask:
                # the proxy sampled outside the format's own width
                bad += 1
                continue
            try:
                got = fn_op(fmt, a, b) & mask
            except Exception:                     # noqa: BLE001
                raised += 1
                continue
            if got != exp:
                bad += 1
                if first is None:
                    first = (a, b, exp, got)
        n = len(doc["vectors"])
        tot_v += n
        tot_bad += bad
        rows.append((fn, key, op, width, bad, raised, n, first))

    rows.sort(key=lambda r: (-r[4] / max(1, r[6]), r[0]))
    print("%-30s %-14s %-6s %5s  %-18s %s"
          % ("pack", "format", "op", "width", "disagree/total", "first disagreement"))
    for fn, key, op, width, bad, raised, n, first in rows:
        pct = 100.0 * bad / n if n else 0.0
        f = "" if first is None else ("a=%d b=%d proxy=%d oracle=%d" % first)
        print("%-30s %-14s %-6s %5d  %6d/%-6d %5.1f%%  %s"
              % (fn, key, op, width, bad, n, pct, f))
    print()
    print("packs from the fp32 proxy      : %d" % len(rows))
    print("vectors in them                : %d" % tot_v)
    print("disagreeing with the oracle    : %d  (%.1f%%)"
          % (tot_bad, 100.0 * tot_bad / max(1, tot_v)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
