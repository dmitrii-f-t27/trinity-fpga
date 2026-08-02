#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_vectors.py — Generator of ADD, MUL and SUB conformance vectors for ALL
oracle formats across the 15 reference modules (gf, tekum, posit, bf16, fp8,
mxfp, takum, decimal, ieee, legacy, lns, int, nf4, gfternary, extended).

For each format and each operation emits:
    conformance/vectors/{format}_{op}.json   where op in {add, mul, sub}
  {
    "format": "gf16",
    "operation": "add" | "mul" | "sub",
    "oracle": "gf_ref.py",
    "family": "gf",
    "width": 16,
    "specials": {"pos_zero":"0x0000", "neg_zero":"0x8000", ...},
    "note": "...",
    "vectors": [ {"a":"0x...","b":"0x...","expected":"0x..."}, ... ]
  }

Coverage policy per format width W (same for ADD, MUL and SUB):
  W <= 8  : exhaustive (all 2^W x 2^W ordered pairs) + edge x edge
  W <= 16 : edge x edge + 200 seeded random pairs
  W >  16 : edge x edge + 50 seeded random pairs (Fraction arithmetic is slow)

Edge coverage naturally exercises the MUL identities: 0*x=0, 1*x=x, max*max
(overflow / saturation), denormal*normal — because edge_raws() always includes
the encoded raws for 0, +/-1, +/-max-finite and a tiny denormal-magnitude value.

Specials (Inf/NaN/NaR) are exposed both (a) as a named legend under "specials"
and (b) as raw hex bit-patterns inside vectors (the DUT sees bits, produces bits).

A format/op is skipped ONLY if that op's function is genuinely absent in the
module. All 15 modules define both add and mul, so every signed format gets an
_add.json, a _mul.json and a _sub.json. SUB is computed as ADD(a, negate(b)),
so no separate oracle function is required; it reuses the exact-Fraction ADD
oracle. Negation is family-aware (see negate_raw):
  * sign-magnitude floats (gf, ieee, bf16, fp8, mxfp, decimal, legacy,
    extended, lns, takum, tekum): flip the sign bit (MSB);
  * two's-complement full-word (posit): (0 - raw) & mask;
  * signed integers (two's complement): (0 - raw) & mask  (modular);
  * code-table formats (nf4, gfternary): encode(-decode(raw));
  * unsigned integers (uint*, bcd): SUB is undefined -> skipped.

Note: LNS MUL is exact in the log domain (log_a + log_b, then RNE) — the
transcendental step is LNS ADD, not MUL; all three ops are emitted and the
distinction is recorded in the per-file "note".

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
    ("gf_ref",        "gf_add",      "gf_mul",      "gf"),
    ("tekum_ref",     "tekum_add",   "tekum_mul",   "tekum"),
    ("posit_ref",     "format_add",  "format_mul",  "posit"),
    ("bf16_ref",      "format_add",  "format_mul",  "bfloat"),
    ("fp8_ref",       "format_add",  "format_mul",  "fp8"),
    ("mxfp_ref",      "format_add",  "format_mul",  "mxfp"),
    ("takum_ref",     "format_add",  "format_mul",  "takum"),
    ("decimal_ref",   "format_add",  "format_mul",  "decimal"),
    ("ieee_ref",      "format_add",  "format_mul",  "ieee"),
    ("legacy_ref",    "format_add",  "format_mul",  "legacy"),
    ("lns_ref",       "format_add",  "format_mul",  "lns"),
    ("int_ref",       "format_add",  "format_mul",  "int"),
    ("nf4_ref",       "format_add",  "format_mul",  "nf4"),
    ("gfternary_ref", "format_add",  "format_mul",  "gfternary"),
    ("extended_ref",  "format_add",  "format_mul",  "extended"),
]

# (op_tag, mode)
#   "add"/"mul" -> direct oracle call via the module's add/mul function
#   "sub"       -> SUB = ADD(a, negate(b)); reuses the ADD oracle (see negate_raw).
#                  Undefined for unsigned integer formats (uint*, bcd) -> skipped.
OPERATIONS = [("add", "add"), ("mul", "mul"), ("sub", "sub")]

# Per-family notes, split by operation. The LNS distinction matters: MUL is the
# exact log-domain operation; ADD is the one with a transcendental step. SUB
# inherits ADD's per-family caveats (it IS add + negate).
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
    if op == "mul":
        table = _MUL_NOTES
        verb = "decode/mul/encode"
    elif op == "sub":
        table = _ADD_NOTES
        verb = "decode/sub/encode (SUB = ADD(a, negate(b)))"
    else:
        table = _ADD_NOTES
        verb = "decode/add/encode"
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
        # Same guard the fp8 branch above already has, and it was missing here.
        # OCP Microscaling v1.0 gives FP4 E2M1 and FP6 E2M3/E3M2 no Inf and no NaN, and
        # mxfp_ref agrees: has_inf False and nan_at_max_only False for all four. The
        # unconditional add put a "quiet_nan" in the published legend of every one --
        # mxfp4's pointed at 0x7, which decodes to 6; mxfp6's and mxgf6's at 4.5;
        # mxgf4's at 2.5. Ordinary finite numbers, labelled NaN in pack metadata.
        if getattr(fmt, "kind", "") != "int":
            if getattr(fmt, "has_inf", False) or getattr(fmt, "nan_at_max_only", False):
                add("quiet_nan")
            if getattr(fmt, "has_inf", False):
                add("pos_inf")
                add("neg_inf")
    elif family == "extended":
        # double_double / quad_double: IEEE-style specials in the hi-limb.
        add("pos_inf")
        add("neg_inf")
        add("quiet_nan")
    elif family == "legacy":
        # x87 is IEEE 754 double-extended and has infinities and NaNs like any other IEEE
        # format. The rest of the legacy family genuinely does not, and legacy_ref raises
        # AttributeError if asked, so `add` sees no attribute and adds nothing.
        #
        # Until pass 186 this branch did not exist and the comment below read "legacy ...
        # decode never yields a Special" -- true of VAX, IBM HFP, MBF and Cray, carried
        # one format too far. It was the third place the same over-general sentence had
        # been written down, after legacy_ref._sat_raw's comment and its decode.
        #
        # It also made the gap self-concealing: edge codes are built through the oracle,
        # so a format whose specials are unimplemented cannot contribute a special edge,
        # and 0 of 3,795 x87 vectors touched an all-ones exponent. Nothing looked missing.
        if getattr(fmt, "kind", "") == "x87":
            add("pos_inf")
            add("neg_inf")
            add("quiet_nan")
    # int / nf4 / gfternary: decode never yields a Special
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


def negate_raw(fmt, mod, family, raw, mask):
    """Return the raw bit-pattern of -value(raw), family-aware. Used for SUB.

    SUB = ADD(a, negate(b)). Negation rules (derived from each oracle's decode):
      * sign-magnitude floats (gf, ieee, bf16, fp8, mxfp, decimal, legacy,
        extended, lns, takum, tekum): flip the sign bit (MSB = bit width-1).
        Correct for every finite value and for Inf/NaN/NaR (flip turns +Inf into
        -Inf, +0 into -0, leaves NaN a NaN).
      * posit: negation is the two's complement of the FULL word, so
        (0 - raw) & mask (matches posit_ref decode: mag = (1<<n) - raw when S=1).
      * signed integers (two's complement): (0 - raw) & mask -> modular negate.
      * code-table formats (nf4, gfternary): encode(-decode(raw)).
      * unsigned integers (uint*, bcd): SUB is undefined -> return None; the
        caller skips emitting a _sub.json for these formats.

    LNS encodes zero (sign 0) and NaR (sign 1) in the SAME field_min pattern, so
    a bare sign flip would swap zero<->NaR; those two specials are pinned here.
    """
    raw &= mask

    if is_int_family(fmt):
        if not getattr(fmt, "signed", False):
            return None                     # unsigned: SUB not defined
        return (0 - raw) & mask             # two's complement (modular)

    if family == "posit":
        return (0 - raw) & mask             # posit negate = 2's complement of word

    if family in ("nf4", "gfternary"):
        return mod.encode(fmt, -mod.decode(fmt, raw)) & mask

    if family == "lns":
        nar = getattr(fmt, "nar", None)
        if nar is not None and raw == (nar & mask):
            return nar & mask               # -NaR = NaR
        field_mask = getattr(fmt, "field_mask", None)
        field_min = getattr(fmt, "field_min", None)
        if field_mask is not None and field_min is not None \
                and (raw & field_mask) == (field_min & field_mask):
            return getattr(fmt, "pos_zero", 0) & mask   # -0 = +0 (LNS has no -0)

    # sign-magnitude float families: flip the MSB
    sign_bit = 1 << (get_width(fmt) - 1)
    return (raw ^ sign_bit) & mask


def make_sub_fn(add_fn, mod, family):
    """Return an op-fn implementing SUB = ADD(a, negate(b)) via the ADD oracle."""
    def sub_fn(fmt, a_raw, b_raw):
        nb = negate_raw(fmt, mod, family, b_raw, get_mask(fmt))
        return add_fn(fmt, a_raw, nb)
    return sub_fn


def structural_raws(fmt, mod, family, width, mask):
    """Codes a format's own definition excludes, built from bits rather than from values.

    Every random operand for a format wider than the cut in gen_pairs comes from
    `_rand_value_raw`, which encodes a random VALUE. That was a cost decision -- raw bits
    for a wide format would demand pow2(huge) -- and it silently fixed the coverage: no
    vector could hold a code outside the image of encode().

    Those codes exist in quantity. research/audit_operand_reachability.py counts them:
    1.26e15 non-canonical BID coefficients in decimal64, 2.98e33 in decimal128, 3.02e23
    x87 unnormals in fp80. Not one appeared in any vector, and pass 185's canonicality
    defect was findable only in decimal32 -- the single format sitting on the width
    boundary where raw-random operands are still drawn.

    Constructing these is cheap even where decoding a *random* wide code is not: a
    non-canonical BID coefficient decodes to zero by IEEE 754-2008 3.5.2, and the x87
    patterns here are pinned to small exponents on purpose. Cost was never the objection
    to covering them; nobody had asked.
    """
    out = set()
    if family == "decimal":
        # Case B above max_coeff: non-canonical, value zero. Take the first, the last and
        # the midpoint of the excluded run rather than a sample, so the set is stable.
        lo = fmt.max_coeff + 1
        hi = ((0b100 << (fmt.coeff_bits_big - 3))
              | ((1 << (fmt.coeff_bits_big - 3)) - 1))
        if hi >= lo:
            for C in (lo, hi, (lo + hi) // 2):
                lower = fmt.coeff_bits_big - 3
                code = ((0b11 << (fmt.sign_shift - 2))
                        | ((fmt.bias & fmt.exp_max) << lower)
                        | (C & ((1 << lower) - 1)))
                out.add(code & mask)
                out.add((code | (1 << fmt.sign_shift)) & mask)
    elif family == "legacy" and getattr(fmt, "kind", "") == "x87":
        m = fmt.mant_bits
        for exp in (1, fmt.bias, fmt.exp_max):
            base = (exp << m) & mask
            out.add(base)                                   # integer bit clear
            out.add((base | 1) & mask)                      # ...with a fraction
            out.add((base | (1 << fmt.sign_shift)) & mask)  # ...negative
    elif family == "legacy" and getattr(fmt, "kind", "") == "vax":
        out.add((1 << fmt.sign_shift) & mask)               # the reserved operand
        out.add(((1 << fmt.sign_shift) | 0x1234) & mask)    # ...with a fraction
    elif family == "extended":
        # Overlapping expansions: a correct value through limbs that are not a
        # nonoverlapping expansion, so the pair is not a member of the format. 0.5 + 0.5
        # sums to exactly 1 and fails, because fl(0.5 + 0.5) is 1.0 rather than 0.5 --
        # the leading limb does not absorb its own tail. Built here rather than counted in
        # audit_operand_reachability, which reports this family as not countable.
        half = mod._encode_binary64(Fraction(1, 2))
        one = mod._encode_binary64(Fraction(1))
        quarter = mod._encode_binary64(Fraction(1, 4))
        out.add((half | (half << 64)) & mask)
        out.add((one | (half << 64)) & mask)
        out.add((half | (quarter << 64)) & mask)
        if fmt.n_limbs >= 4:
            out.add((half | (half << 64) | (half << 128) | (half << 192)) & mask)
    return sorted(out)


def edge_raws(fmt, mod, family, width, mask):
    """Representative raw bit-patterns: real specials + encoded boundary values."""
    raws = set()

    # 1. real specials (structural, decode-safe — see real_specials)
    for _attr, raw in real_specials(fmt, family, width):
        raws.add(raw)

    # 1b. codes the format excludes. See structural_raws: without these, a format wider
    # than gen_pairs' raw-random cut can only ever be tested on the image of encode().
    for raw in structural_raws(fmt, mod, family, width, mask):
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
    # The seed is INDEPENDENT of the operation, so {format}_add.json,
    # {format}_mul.json and {format}_sub.json exercise the SAME (a, b) input
    # pairs — only the expected output differs. This keeps ADD/MUL vectors
    # byte-identical to the previous generator and makes cross-op checks trivial.
    files_written = []
    total_vectors = 0
    total_errors = 0
    skipped = []
    per_format = []   # (fname, family, width, counts_dict)

    t0 = time.time()

    # First pass: import every module once, resolve its op fns, then iterate.
    for mi, (mod_name, add_name, mul_name, family) in enumerate(MODULES):
        mod = importlib.import_module(mod_name)

        add_fn = getattr(mod, add_name, None)
        mul_fn = getattr(mod, mul_name, None)
        # SUB reuses the ADD oracle with a negated second operand.
        sub_fn = make_sub_fn(add_fn, mod, family) if add_fn is not None else None
        if add_fn is None:
            for fname in mod.FORMATS:
                skipped.append(f"{fname}/add (no {add_name} in {mod_name})")
        if mul_fn is None:
            for fname in mod.FORMATS:
                skipped.append(f"{fname}/mul (no {mul_name} in {mod_name})")

        for fname, fmt in mod.FORMATS.items():
            seed = (mi + 1) * 100003 + sum(ord(c) for c in fname)
            ft0 = time.time()
            counts = {}
            for op, mode in OPERATIONS:
                if mode == "add":
                    fn = add_fn
                elif mode == "mul":
                    fn = mul_fn
                else:  # sub
                    fn = sub_fn
                    # SUB undefined for unsigned integer formats -> skip.
                    if is_int_family(fmt) and not getattr(fmt, "signed", False):
                        skipped.append(f"{fname}/sub (unsigned int: SUB undefined)")
                        counts[op] = None
                        continue
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
            per_format.append((fname, family, get_width(fmt), counts))
            n_add = counts.get("add")
            n_mul = counts.get("mul")
            n_sub = counts.get("sub")
            print(f"  {fname:<14} w={get_width(fmt):>3}  "
                  f"add={str(n_add):>7}  mul={str(n_mul):>7}  sub={str(n_sub):>7}  "
                  f"({time.time()-ft0:.1f}s)", flush=True)

    dt = time.time() - t0

    # ---------------- report ----------------
    print("=" * 82)
    print("TRINITY conformance vector generator (AGENT F) — ADD + MUL + SUB operations")
    print("=" * 82)
    print(f"{'format':<14}{'family':<9}{'width':>6}{'add':>10}{'mul':>10}{'sub':>10}")
    print("-" * 82)
    n_add_files = n_mul_files = n_sub_files = 0
    for fname, fam, w, counts in per_format:
        na, nm, ns = counts.get("add"), counts.get("mul"), counts.get("sub")
        print(f"{fname:<14}{fam:<9}{w:>6}{str(na):>10}{str(nm):>10}{str(ns):>10}")
        if na is not None:
            n_add_files += 1
        if nm is not None:
            n_mul_files += 1
        if ns is not None:
            n_sub_files += 1
    print("-" * 82)
    print(f"formats covered : {len(per_format)}")
    print(f"_add.json files : {n_add_files}")
    print(f"_mul.json files : {n_mul_files}")
    print(f"_sub.json files : {n_sub_files}  (unsigned ints skipped: SUB undefined)")
    print(f"files written   : {len(files_written)}  -> {VECTORS_DIR}")
    print(f"total vectors   : {total_vectors}")
    print(f"skipped (op/fmt): {len(skipped)}")
    for s in skipped:
        print(f"    - {s}")
    if total_errors:
        print(f"vector errors   : {total_errors} (pairs that raised and were dropped)")
    print(f"elapsed         : {dt:.1f}s")
    print("=" * 82)
    return 0


if __name__ == "__main__":
    sys.exit(main())
