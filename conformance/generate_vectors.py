#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_vectors.py — Generator of ADD and MUL conformance vectors for ALL 72
oracle formats across the 12 reference modules (gf, tekum, posit, bf16, fp8,
mxfp, takum, decimal, ieee, legacy, lns, int).

For each format and each operation emits:
    conformance/vectors/{format}_{op}.json   where op in {add, mul}
  {
    "format": "gf16",
    "operation": "add" | "mul",
    "oracle": "gf_ref.py",
    "family": "gf",
    "width": 16,
    "specials": {"pos_zero":"0x0000", "neg_zero":"0x8000", ...},
    "note": "...",
    "vectors": [ {"a":"0x...","b":"0x...","expected":"0x..."}, ... ]
  }

Coverage policy per format width W (same for ADD and MUL):
  W <= 8  : exhaustive (all 2^W x 2^W ordered pairs) + edge x edge
  W <= 16 : edge x edge + 200 seeded random pairs
  W >  16 : edge x edge + 50 seeded random pairs (Fraction arithmetic is slow)

Edge coverage naturally exercises the MUL identities: 0*x=0, 1*x=x, max*max
(overflow / saturation), denormal*normal — because edge_raws() always includes
the encoded raws for 0, +/-1, +/-max-finite and a tiny denormal-magnitude value.

Specials (Inf/NaN/NaR) are exposed both (a) as a named legend under "specials"
and (b) as raw hex bit-patterns inside vectors (the DUT sees bits, produces bits).

A format/op is skipped ONLY if that op's function is genuinely absent in the
module. All 12 modules define both add and mul, so all 72 formats get both an
_add.json and a _mul.json. Note: LNS MUL is exact in the log domain
(log_a + log_b, then RNE) — the transcendental step is LNS ADD, not MUL; both
are emitted and the distinction is recorded in the per-file "note".

Honesty: Trinity conformance team (AGENT F). Run: python3 conformance/generate_vectors.py
"""

import importlib
import json
import os
import random
import sys
import time
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))          # .../conformance
VECTORS_DIR = os.path.join(HERE, "vectors")

# (module_name, add_function_name, mul_function_name, family_tag)
MODULES = [
    ("gf_ref",      "gf_add",      "gf_mul",      "gf"),
    ("tekum_ref",   "tekum_add",   "tekum_mul",   "tekum"),
    ("posit_ref",   "format_add",  "format_mul",  "posit"),
    ("bf16_ref",    "format_add",  "format_mul",  "bfloat"),
    ("fp8_ref",     "format_add",  "format_mul",  "fp8"),
    ("mxfp_ref",    "format_add",  "format_mul",  "mxfp"),
    ("takum_ref",   "format_add",  "format_mul",  "takum"),
    ("decimal_ref", "format_add",  "format_mul",  "decimal"),
    ("ieee_ref",    "format_add",  "format_mul",  "ieee"),
    ("legacy_ref",  "format_add",  "format_mul",  "legacy"),
    ("lns_ref",     "format_add",  "format_mul",  "lns"),
    ("int_ref",     "format_add",  "format_mul",  "int"),
]

# (op_tag, index_into_module_tuple_for_fn_name)
OPERATIONS = [("add", 1), ("mul", 2)]

# Per-family notes, split by operation. The LNS distinction matters: MUL is the
# exact log-domain operation; ADD is the one with a transcendental step.
_ADD_NOTES = {
    "lns": "lns add uses a transcendental step (math.log2); result is the "
           "oracle's rounded-log approximation, not exact-Fraction.",
    "takum": "Linear structural model of tapered takum (see takum_ref.py).",
    "tekum": "Linear structural model of tapered tekum (see tekum_ref.py).",
}
_MUL_NOTES = {
    "lns": "lns mul is EXACT in the log domain (log_a + log_b as Fractions, "
           "then RNE) — no transcendental step (unlike lns add).",
    "takum": "Linear structural model of tapered takum (see takum_ref.py).",
    "tekum": "Linear structural model of tapered tekum (see tekum_ref.py).",
}


def op_note(family, op):
    table = _MUL_NOTES if op == "mul" else _ADD_NOTES
    verb = "decode/mul/encode" if op == "mul" else "decode/add/encode"
    return table.get(family, f"exact Fraction {verb}, round-ties-even.")

def hexstr(raw, width):
    ndig = (width + 3) // 4
    return f"0x{raw & ((1 << width) - 1):0{ndig}X}"


def real_specials(fmt, family, width):
    """List of (attr, raw) for specials this format GENUINELY represents.

    Deciding membership structurally (by family + format flags) rather than by
    probing decode() is essential: non-Inf GF formats still expose pos_inf /
    quiet_nan *properties*, but their decode treats those bit patterns as finite
    values with exponent exp_max-bias (~2^(2^48) for gf128) — decoding them
    would hang wide formats forever. """
    mask = get_mask(fmt)
    out = []

    def add(attr):
        v = getattr(fmt, attr, None)
        if v is not None:
            out.append((attr, v & mask))

    # zero-class specials are always real and always safe to decode
    add("pos_zero")
    add("neg_zero")

    if family in ("posit", "takum", "tekum", "lns"):
        add("nar")
    elif family in ("ieee", "bfloat", "decimal"):
        add("pos_inf")
        add("neg_inf")
        add("quiet_nan")
    elif family == "gf":
        if getattr(fmt, "has_inf", False):   # only gf16
            add("pos_inf")
            add("neg_inf")
            add("quiet_nan")
    elif family == "fp8":
        if getattr(fmt, "has_inf", False):
            add("pos_inf")
            add("neg_inf")
        if getattr(fmt, "has_inf", False) or getattr(fmt, "nan_at_max_only", False):
            add("quiet_nan")
    elif family == "mxfp":
        if getattr(fmt, "kind", "") != "int":
            add("quiet_nan")
            if getattr(fmt, "has_inf", False):
                add("pos_inf")
                add("neg_inf")
    # legacy / int: decode never yields a Special
    return out


def specials_legend(fmt, family, width):
    return {attr: hexstr(raw, width) for attr, raw in real_specials(fmt, family, width)}


def get_width(fmt):
    return getattr(fmt, "width")


def get_mask(fmt):
    m = getattr(fmt, "mask", None)
    if m is not None:
        return m
    return (1 << get_width(fmt)) - 1


def is_int_family(fmt):
    return hasattr(fmt, "signed")


def edge_raws(fmt, mod, family, width, mask):
    """Representative raw bit-patterns: real specials + encoded boundary values."""
    raws = set()

    # 1. real specials (structural, decode-safe — see real_specials)
    for _attr, raw in real_specials(fmt, family, width):
        raws.add(raw)

    enc = mod.encode

    if is_int_family(fmt):
        # integer family: encode requires exact integer values
        mx = fmt.max_val
        mn = fmt.min_val
        for v in (0, 1, -1, 2, -2, mx, mn, mx - 1, mn + 1):
            try:
                raws.add(enc(fmt, v) & mask)
            except Exception:
                pass
        return sorted(raws)

    # 2. float-ish family: encode representative exact Fractions
    test_values = [
        Fraction(1), Fraction(-1),
        Fraction(2), Fraction(-2),
        Fraction(1, 2), Fraction(-1, 2),
        Fraction(3), Fraction(-3),
        Fraction(1, 3), Fraction(2, 3),
        Fraction(1, 4), Fraction(-1, 4),
        Fraction(10), Fraction(-10),
    ]
    for tv in test_values:
        try:
            raws.add(enc(fmt, tv) & mask)
        except Exception:
            pass

    # 3. large magnitude -> max-finite (saturation formats) or Inf (inf formats)
    for tv in (Fraction(1 << 200), Fraction(1 << 400), Fraction(-(1 << 200))):
        try:
            raws.add(enc(fmt, tv) & mask)
        except Exception:
            pass

    # 4. tiny magnitude -> exercises gradual underflow / min denormal / flush-to-zero
    for tv in (Fraction(1, 1 << 30), Fraction(1, 1 << 60), Fraction(-1, 1 << 40)):
        try:
            raws.add(enc(fmt, tv) & mask)
        except Exception:
            pass

    return sorted(raws)


def _rand_nice_fraction(rng):
    """Bounded-complexity Fraction whose unbiased binary exponent stays small
    (roughly [-50, 50]). This keeps decode/encode cheap even for ultra-wide
    formats (gf64/128/256) where a fully-random raw would demand pow2(2^97)
    and hang forever."""
    den = rng.choice([1, 2, 4, 8, 16, 3, 5, 10, 32, 64, 100, 128])
    int_part = rng.randint(-16, 16)
    num = int_part * den + rng.randint(-den + 1, den - 1)
    base = Fraction(num, den)
    k = rng.randint(-40, 40)                       # bounded power-of-two scale
    scale = Fraction(1 << k, 1) if k >= 0 else Fraction(1, 1 << (-k))
    return base * scale


def _rand_value_raw(rng, fmt, mod, mask):
    """Encode a nice bounded Fraction -> raw. Safe for any width."""
    for _ in range(8):
        try:
            return mod.encode(fmt, _rand_nice_fraction(rng)) & mask
        except Exception:
            continue
    return getattr(fmt, "pos_zero", 0) & mask


def gen_pairs(fmt, mod, family, width, mask, seed):
    """Yield ordered (a_raw, b_raw) pairs per the coverage policy.

    width <= 8            : exhaustive (all 2^W x 2^W pairs) + edge x edge
    width <= 16           : edge x edge + 200 random pairs
    width >  16 (int)     : edge x edge + 50 raw-random pairs (ints are cheap)
    width >  16 (float)   : edge x edge + 50 pairs; raw-random for W<=32,
                            value-driven for W>32 (avoids pow2(huge) blowup).
    """
    rng = random.Random(seed)
    edges = edge_raws(fmt, mod, family, width, mask)

    pairs = []
    seen = set()

    def emit(a, b):
        a &= mask
        b &= mask
        key = (a, b)
        if key not in seen:
            seen.add(key)
            pairs.append(key)

    # edge x edge
    for a in edges:
        for b in edges:
            emit(a, b)

    space = 1 << width

    if width <= 8:
        # exhaustive over the full coding space
        for a in range(space):
            for b in range(space):
                emit(a, b)
        return pairs

    n_rand = 200 if width <= 16 else 50

    if is_int_family(fmt):
        raws = [rng.randrange(space) for _ in range(n_rand)]
    elif width <= 32:
        raws = [rng.randrange(space) for _ in range(n_rand)]
    else:
        # value-driven: bounded unbiased exponent -> decode/encode stay cheap
        raws = [_rand_value_raw(rng, fmt, mod, mask) for _ in range(n_rand)]

    pool = raws + edges[:min(8, len(edges))]
    for _ in range(n_rand):
        emit(pool[rng.randrange(len(pool))], pool[rng.randrange(len(pool))])
    for r in raws:
        emit(r, 0)
        emit(0, r)

    return pairs


def build_document(name, fmt, mod, op_fn, op, family, oracle_file, seed):
    width = get_width(fmt)
    mask = get_mask(fmt)

    pairs = gen_pairs(fmt, mod, family, width, mask, seed)

    vectors = []
    errors = 0
    for a_raw, b_raw in pairs:
        try:
            exp_raw = op_fn(fmt, a_raw, b_raw) & mask
        except Exception:
            errors += 1
            continue
        vectors.append({
            "a": hexstr(a_raw, width),
            "b": hexstr(b_raw, width),
            "expected": hexstr(exp_raw, width),
        })

    doc = {
        "format": name,
        "operation": op,
        "oracle": oracle_file,
        "family": family,
        "width": width,
        "specials": specials_legend(fmt, family, width),
        "note": op_note(family, op),
        "vector_count": len(vectors),
        "vectors": vectors,
    }
    return doc, errors


def main():
    sys.path.insert(0, HERE)
    os.makedirs(VECTORS_DIR, exist_ok=True)

    # Deterministic per-format seeds derived from (module index, format name).
    # The seed is INDEPENDENT of the operation, so {format}_add.json and
    # {format}_mul.json exercise the SAME (a, b) input pairs — only the
    # expected output differs. This keeps ADD vector byte-identical to the
    # previous (add-only) generator and makes add-vs-mul cross-checks trivial.
    files_written = []
    total_vectors = 0
    total_errors = 0
    skipped = []
    per_format = []   # (fname, family, width, n_add, n_mul)

    t0 = time.time()

    # First pass: import every module once, resolve its op fns, then iterate.
    for mi, (mod_name, add_name, mul_name, family) in enumerate(MODULES):
        mod = importlib.import_module(mod_name)

        # resolve operation functions; if a module lacks an op, skip all its
        # formats for that op with an explicit message (none do today).
        op_fns = {}
        for op, fn_idx in OPERATIONS:
            fn_name = (add_name, mul_name)[fn_idx - 1]
            fn = getattr(mod, fn_name, None)
            if fn is None:
                for fname in mod.FORMATS:
                    skipped.append(f"{fname}/{op} (no {fn_name} in {mod_name})")
            else:
                op_fns[op] = fn

        for fname, fmt in mod.FORMATS.items():
            seed = (mi + 1) * 100003 + sum(ord(c) for c in fname)
            ft0 = time.time()
            counts = {}
            for op, _ in OPERATIONS:
                fn = op_fns.get(op)
                if fn is None:
                    counts[op] = None
                    continue
                try:
                    doc, errs = build_document(fname, fmt, mod, fn, op, family,
                                               f"{mod_name}.py", seed)
                except Exception as e:
                    skipped.append(f"{fname}/{op} (generation error: {e!r})")
                    print(f"  [SKIP] {fname}/{op}: {e!r}", flush=True)
                    counts[op] = None
                    continue
                out_path = os.path.join(VECTORS_DIR, f"{fname}_{op}.json")
                with open(out_path, "w") as f:
                    json.dump(doc, f)
                files_written.append(out_path)
                total_vectors += doc["vector_count"]
                total_errors += errs
                counts[op] = doc["vector_count"]
            per_format.append((fname, family, get_width(fmt), counts.get("add"), counts.get("mul")))
            n_add = counts.get("add")
            n_mul = counts.get("mul")
            print(f"  {fname:<14} w={get_width(fmt):>3}  "
                  f"add={str(n_add):>7}  mul={str(n_mul):>7}  "
                  f"({time.time()-ft0:.1f}s)", flush=True)

    dt = time.time() - t0

    # ---------------- report ----------------
    print("=" * 72)
    print("TRINITY conformance vector generator (AGENT F) — ADD + MUL operations")
    print("=" * 72)
    print(f"{'format':<14}{'family':<9}{'width':>6}{'add':>10}{'mul':>10}")
    print("-" * 72)
    n_add_files = n_mul_files = 0
    for fname, fam, w, na, nm in per_format:
        print(f"{fname:<14}{fam:<9}{w:>6}{str(na):>10}{str(nm):>10}")
        if na is not None:
            n_add_files += 1
        if nm is not None:
            n_mul_files += 1
    print("-" * 72)
    print(f"formats covered : {len(per_format)}")
    print(f"_add.json files : {n_add_files}")
    print(f"_mul.json files : {n_mul_files}")
    print(f"files written   : {len(files_written)}  -> {VECTORS_DIR}")
    print(f"total vectors   : {total_vectors}")
    print(f"skipped (op/fmt): {len(skipped)}")
    for s in skipped:
        print(f"    - {s}")
    if total_errors:
        print(f"vector errors   : {total_errors} (pairs that raised and were dropped)")
    print(f"elapsed         : {dt:.1f}s")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
