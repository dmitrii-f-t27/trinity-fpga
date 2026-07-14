#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_vectors.py — Generator of ADD conformance vectors for ALL 72 oracle
formats across the 12 reference modules (gf, tekum, posit, bf16, fp8, mxfp,
takum, decimal, ieee, legacy, lns, int).

For each format emits conformance/vectors/{format}_add.json:
  {
    "format": "gf16",
    "operation": "add",
    "oracle": "gf_ref.py",
    "family": "gf",
    "width": 16,
    "specials": {"pos_zero":"0x0000", "neg_zero":"0x8000", ...},
    "note": "...",
    "vectors": [ {"a":"0x...","b":"0x...","expected":"0x..."}, ... ]
  }

Coverage policy per format width W:
  W <= 8  : exhaustive (all 2^W x 2^W ordered pairs) + edge x edge
  W <= 16 : edge x edge + 200 seeded random pairs
  W >  16 : edge x edge + 50 seeded random pairs (Fraction arithmetic is slow)

Specials (Inf/NaN/NaR) are exposed both (a) as a named legend under "specials"
and (b) as raw hex bit-patterns inside vectors (the DUT sees bits, produces bits).

Skips a format only if its add function is genuinely absent. All 12 modules
define add, so all 72 formats are covered (lns add is transcendental/approximate
but defined — noted in the per-file "note").

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

# (module_name, add_function_name, family_tag)
MODULES = [
    ("gf_ref",      "gf_add",      "gf"),
    ("tekum_ref",   "tekum_add",   "tekum"),
    ("posit_ref",   "format_add",  "posit"),
    ("bf16_ref",    "format_add",  "bfloat"),
    ("fp8_ref",     "format_add",  "fp8"),
    ("mxfp_ref",    "format_add",  "mxfp"),
    ("takum_ref",   "format_add",  "takum"),
    ("decimal_ref", "format_add",  "decimal"),
    ("ieee_ref",    "format_add",  "ieee"),
    ("legacy_ref",  "format_add",  "legacy"),
    ("lns_ref",     "format_add",  "lns"),
    ("int_ref",     "format_add",  "int"),
]

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


def build_document(name, fmt, mod, add_fn, family, oracle_file, seed):
    width = get_width(fmt)
    mask = get_mask(fmt)

    pairs = gen_pairs(fmt, mod, family, width, mask, seed)

    vectors = []
    errors = 0
    for a_raw, b_raw in pairs:
        try:
            exp_raw = add_fn(fmt, a_raw, b_raw) & mask
        except Exception:
            errors += 1
            continue
        vectors.append({
            "a": hexstr(a_raw, width),
            "b": hexstr(b_raw, width),
            "expected": hexstr(exp_raw, width),
        })

    note = {
        "lns": "lns add uses a transcendental step (math.log2); result is the "
               "oracle's rounded-log approximation, not exact-Fraction.",
        "takum": "Linear structural model of tapered takum (see takum_ref.py).",
        "tekum": "Linear structural model of tapered tekum (see tekum_ref.py).",
    }.get(family, "exact Fraction decode/add/encode, round-ties-even.")

    doc = {
        "format": name,
        "operation": "add",
        "oracle": oracle_file,
        "family": family,
        "width": width,
        "specials": specials_legend(fmt, family, width),
        "note": note,
        "vector_count": len(vectors),
        "vectors": vectors,
    }
    return doc, errors


def main():
    sys.path.insert(0, HERE)
    os.makedirs(VECTORS_DIR, exist_ok=True)

    # Deterministic per-format seeds derived from (module index, format name).
    files_written = []
    total_vectors = 0
    total_errors = 0
    skipped = []
    per_format = []

    t0 = time.time()

    for mi, (mod_name, add_name, family) in enumerate(MODULES):
        mod = importlib.import_module(mod_name)
        add_fn = getattr(mod, add_name, None)
        if add_fn is None:
            for fname in mod.FORMATS:
                skipped.append(f"{fname} (no {add_name} in {mod_name})")
            continue

        for fname, fmt in mod.FORMATS.items():
            seed = (mi + 1) * 100003 + sum(ord(c) for c in fname)
            ft0 = time.time()
            try:
                doc, errs = build_document(fname, fmt, mod, add_fn, family,
                                           f"{mod_name}.py", seed)
            except Exception as e:
                skipped.append(f"{fname} (generation error: {e!r})")
                print(f"  [SKIP] {fname}: {e!r}", flush=True)
                continue
            out_path = os.path.join(VECTORS_DIR, f"{fname}_add.json")
            with open(out_path, "w") as f:
                json.dump(doc, f)
            files_written.append(out_path)
            total_vectors += doc["vector_count"]
            total_errors += errs
            per_format.append((fname, family, doc["width"], doc["vector_count"]))
            print(f"  {fname:<14} w={doc['width']:>3}  vectors={doc['vector_count']:>7}  "
                  f"({time.time()-ft0:.1f}s)", flush=True)

    dt = time.time() - t0

    # ---------------- report ----------------
    print("=" * 64)
    print("TRINITY conformance vector generator (AGENT F) — ADD operation")
    print("=" * 64)
    print(f"{'format':<14}{'family':<9}{'width':>6}{'vectors':>12}")
    print("-" * 64)
    for fname, fam, w, nv in per_format:
        print(f"{fname:<14}{fam:<9}{w:>6}{nv:>12}")
    print("-" * 64)
    print(f"formats covered : {len(per_format)}")
    print(f"files written   : {len(files_written)}  -> {VECTORS_DIR}")
    print(f"total vectors   : {total_vectors}")
    print(f"skipped formats : {len(skipped)}")
    for s in skipped:
        print(f"    - {s}")
    if total_errors:
        print(f"vector errors   : {total_errors} (pairs that raised and were dropped)")
    print(f"elapsed         : {dt:.1f}s")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
