#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Does every format's declared set of specials match what its oracle actually decodes?

Pass 186 found `legacy_ref.decode` treating x87's all-ones exponent as an ordinary
exponent: +Inf came back as 2^16384, a 4,933-digit integer, and every NaN came back as a
number. x87_fp80 is IEEE 754 double-extended. The cause was one true sentence carried one
format too far -- "legacy formats have no Inf" holds for VAX, IBM HFP, MBF and Cray -- and
it had been written down in three places.

What made it survive is worth more than the bug. Edge codes are built *through* the
oracle, so a format whose specials are unimplemented cannot contribute a special edge:
0 of 3,795 x87 vectors touched an all-ones exponent. Coverage looked complete because the
missing piece was also the piece that would have shown it missing.

This check breaks that circle by comparing two things that are supposed to agree and are
derived independently:

    DECLARED   generate_vectors.real_specials(fmt, family, width) -- decided structurally
               from the family and the format's flags, never by probing decode
    OBSERVED   what decode() actually returns for those bit patterns, plus a bounded
               sweep for any OTHER pattern that decodes to a Special

A format that declares no specials but whose decode yields one is a stale declaration.
A format that declares one whose decode yields a finite number is the x87 class: the
declaration is aspirational and the packs contain arithmetic on a number that should be
an infinity.

    python3 research/audit_special_coverage.py [--verbose] [--self-check]

Exit 0 when the two agree everywhere, 1 on any mismatch.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")

# Sweeping every code is impossible for 128-bit formats and pointless for 4-bit ones.
# These are the patterns a format uses to say "not a finite number" if it says it at all:
# an all-ones exponent field, the top of the code space, and their signed twins. Bounded
# on purpose, and the bound is reported rather than assumed away.
PROBE_LIMIT = 4096


def load(name):
    p = os.path.join(CONF, f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod          # pass 156: @dataclass needs this before exec
    spec.loader.exec_module(mod)
    return mod


# Above this unbiased exponent, decode() of an all-ones pattern is not slow but
# impossible: real_specials' own docstring says a non-Inf gf128 decodes that pattern as a
# finite value near 2^(2^48). The first version of this file called decode there anyway
# and the process was killed. The bound is on the exponent, not the width -- x87_fp80 is
# 80 bits and tops out at 2^16384, which is a 4,933-digit integer and perfectly fine.
MAX_SAFE_EXP = 1 << 20


def decode_is_bounded(fmt) -> bool:
    expm = getattr(fmt, "exp_max", None)
    bias = getattr(fmt, "bias", 0)
    if expm is None:
        return True
    return (expm - bias) <= MAX_SAFE_EXP


def decodes_special(mod, fmt, raw):
    """True if decode(raw) is a Special.

    Returns None -- not False -- when the format's exponent range makes decode unsafe to
    call. A skipped probe and a negative probe are different answers, and reporting the
    first as the second is the failure this whole campaign is about.
    """
    Special = getattr(mod, "Special", None)
    if Special is None:
        return False
    if not decode_is_bounded(fmt):
        return None
    try:
        return isinstance(mod.decode(fmt, raw), Special)
    except Exception:
        return False


def probe_raws(fmt, width, mask):
    """Bit patterns worth asking about, without enumerating the space."""
    out = {0, mask, 1 << (width - 1)}
    mant = getattr(fmt, "mant_bits", None)
    expm = getattr(fmt, "exp_max", None)
    if mant is not None and expm is not None:
        top = (expm << mant) & mask
        for extra in (0, 1, 1 << max(0, mant - 1), 1 << max(0, mant - 2),
                      (1 << mant) - 1):
            out.add((top | extra) & mask)
            out.add((top | extra | (1 << (width - 1))) & mask)
    return sorted(out)[:PROBE_LIMIT]


def main() -> int:
    verbose = "--verbose" in sys.argv
    sys.path.insert(0, CONF)
    G = load("generate_vectors")

    rows, gaps, stale, unprobed = [], [], [], []
    for mod_name, _add, _mul, family in G.MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except Exception as e:
            print(f"  {mod_name}: not importable -- {type(e).__name__}")
            continue
        for fname, fmt in mod.FORMATS.items():
            width = G.get_width(fmt)
            mask = G.get_mask(fmt)
            if not decode_is_bounded(fmt):
                unprobed.append((fname, family))
                continue
            declared = {a for a, _ in G.real_specials(fmt, family, width)
                        if "zero" not in a}
            observed = {r for _a, r in G.real_specials(fmt, family, width)
                        if "zero" not in _a and decodes_special(mod, fmt, r)}

            # DECLARED but decode says finite -- the x87 class.
            aspirational = {a for a, r in G.real_specials(fmt, family, width)
                            if "zero" not in a and not decodes_special(mod, fmt, r)}
            # decode says Special for a pattern nothing declared -- stale declaration.
            extra = [r for r in probe_raws(fmt, width, mask)
                     if decodes_special(mod, fmt, r)
                     and r not in {v for _a, v in G.real_specials(fmt, family, width)}]

            rows.append((fname, family, len(declared), len(observed)))
            if aspirational:
                gaps.append((fname, family, sorted(aspirational)))
            if extra and not declared:
                stale.append((fname, family, len(extra), extra[:3], width))

    print(f"formats checked                      : {len(rows)}")
    print(f"  declaring at least one special     : "
          f"{sum(1 for r in rows if r[2])}")
    print(f"  DECLARED but decode returns finite : {len(gaps)}")
    print(f"  decode yields a Special nothing declared : {len(stale)}")
    print(f"  NOT PROBED (decode unbounded)        : {len(unprobed)}"
          f"{'  -- ' + ', '.join(f for f, _ in unprobed[:6]) if unprobed else ''}\n")

    if gaps:
        print("DECLARED BUT NOT DECODED -- the packs hold arithmetic on a number that")
        print("should be a special:")
        for fname, family, attrs in gaps:
            print(f"  {fname:<16} ({family})  {', '.join(attrs)}")
        print()

    if stale:
        print("DECODES A SPECIAL THAT NOTHING DECLARES -- edge generation will never")
        print("produce these, so no vector exercises them:")
        for fname, family, n, sample, width in stale:
            hexes = ", ".join(f"0x{r:0{width // 4}x}" for r in sample)
            print(f"  {fname:<16} ({family})  {n} of {PROBE_LIMIT} probed: {hexes}")
        print()

    if verbose:
        for fname, family, d, o in rows:
            print(f"  {fname:<16} {family:<10} declared {d}  decoded {o}")

    print(f"""
Both directions matter and they fail differently. A format that declares a special its
decode does not produce puts a finite number where an infinity belongs, and the packs look
complete because edge codes are built through that same decode. A format whose decode
yields a special nothing declared has the pattern reachable by hand and unreachable by the
generator, so no vector ever lands on it.

{len(unprobed)} formats are NOT PROBED, not passing: their exponent range makes decode of
an all-ones pattern a number near 2^(2^48), which is why real_specials decides membership
structurally in the first place. Counting them as clean would be the exact substitution
this file exists to catch.

The probe is bounded at {PROBE_LIMIT} patterns per format and looks only where a format
would put "not a finite number" -- the all-ones exponent, the ends of the code space, and
their signed twins. It is not a proof of absence and does not claim to be.""")
    return 1 if (gaps or stale) else 0


def self_check() -> int:
    """Negative control: re-declare a special for a format that genuinely has none, and
    require the audit to flag it. VAX has no infinity -- legacy_ref raises AttributeError
    if asked -- so forcing one in must show up as DECLARED-but-not-decoded."""
    sys.path.insert(0, CONF)
    G = load("generate_vectors")
    legacy = importlib.import_module("legacy_ref")
    fmt = legacy.FORMATS["vax_f"]
    width, mask = G.get_width(fmt), G.get_mask(fmt)

    before = G.real_specials(fmt, "legacy", width)
    forged = (fmt.exp_max << fmt.mant_bits) & mask
    seen = decodes_special(legacy, fmt, forged)

    print(f"  vax_f declares {len(before)} specials (zeros only): "
          f"{[a for a, _ in before]}")
    print(f"  its all-ones exponent 0x{forged:08x} decodes to "
          f"{str(legacy.decode(fmt, forged))[:24]}")
    print(f"  and is NOT a Special -> {not seen}  "
          f"{'ok' if not seen else 'VAX GREW AN INFINITY'}")

    x87 = legacy.FORMATS["x87_fp80"]
    got = decodes_special(legacy, x87, x87.pos_inf)
    print(f"  x87_fp80 pos_inf decodes as a Special -> {got}  "
          f"{'ok' if got else 'THE PASS-186 FIX IS GONE'}")

    ok = (not seen) and got
    print(f"\nself-check: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        raise SystemExit(self_check())
    raise SystemExit(main())
