#!/usr/bin/env python3
"""Exhaustive verification of the takum negation fix against libtakum.

libtakum (github.com/takum-arithmetic/libtakum) is the format author's own C99
reference implementation. research/libtakum_bridge.c dumps its decode of every
code as a binary64 bit pattern; this compares the oracle against that dump for
EVERY code, plus checks the two intrinsic properties the fix is supposed to
restore.

Checks, per width:
  1. decode agrees with libtakum on all 2^n codes
  2. the two's-complement negation invariant holds
  3. encode(decode(raw)) == raw for every finite code

Usage:
    /tmp/libtakum_bridge 8  > /tmp/lt8.tsv
    /tmp/libtakum_bridge 16 > /tmp/lt16.tsv
    python3 research/verify_takum_fix.py /tmp/lt8.tsv:takum8 /tmp/lt16.tsv:takum16

Exit: 0 only if every check passes on every width.
"""
from __future__ import annotations
from fractions import Fraction
import importlib.util
import os
import struct
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(REPO, "conformance")


def load_takum():
    sys.path.insert(0, CONF)
    spec = importlib.util.spec_from_file_location("tk", os.path.join(CONF, "takum_ref.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def norm(x):
    """Both sides into one key space: NaN/NaR collapse, zero sign not compared."""
    kind = getattr(x, "kind", None)
    if kind is not None:
        return "nan" if kind in ("nan", "nar") else f"special:{kind}"
    try:
        f = float(x)
    except (TypeError, ValueError, OverflowError):
        return f"opaque:{x!r}"
    if f != f:
        return "nan"
    if f == float("inf"):
        return "+inf"
    if f == float("-inf"):
        return "-inf"
    return "zero" if f == 0.0 else f


def check(mod, fmt_name, dump_path):
    fmt = mod.FORMATS[fmt_name]
    span = 1 << fmt.n
    msb = span >> 1

    ref = {}
    with open(dump_path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                r, h = line.split("\t")
                ref[int(r)] = struct.unpack(">d", bytes.fromhex(h))[0]

    # 1. agreement with libtakum, every code
    mism = []
    for raw in range(span):
        a = norm(mod.decode(fmt, raw))
        b = norm(ref[raw])
        if a != b:
            mism.append(raw)

    # 2. negation invariant
    neg_fail = 0
    for raw in range(span):
        if raw in (0, msb):
            continue
        x = mod.decode(fmt, raw)
        y = mod.decode(fmt, (-raw) % span)
        if getattr(x, "kind", None) or getattr(y, "kind", None):
            continue
        if Fraction(y) != -Fraction(x):
            neg_fail += 1

    # 3. round trip
    rt_fail = 0
    for raw in range(span):
        v = mod.decode(fmt, raw)
        if getattr(v, "kind", None) is not None:
            continue
        if mod.encode(fmt, v) != raw:
            rt_fail += 1

    print(f"{fmt_name:<9} codes={span:<7} "
          f"vs libtakum: {'ALL MATCH' if not mism else str(len(mism)) + ' MISMATCH'}   "
          f"negation: {'HOLDS' if not neg_fail else str(neg_fail) + ' FAIL'}   "
          f"roundtrip: {'OK' if not rt_fail else str(rt_fail) + ' FAIL'}")
    if mism:
        for raw in mism[:5]:
            print(f"    raw=0x{raw:x} ours={norm(mod.decode(fmt, raw))!r} "
                  f"libtakum={norm(ref[raw])!r}")
    return len(mism) + neg_fail + rt_fail


def check_wide(mod, fmt_name, samples=20000):
    """takum32/64 cannot be enumerated. Check the negation invariant on a sample.

    Stated plainly: this is SAMPLED, not exhaustive. The fix is structural — the
    negative half decodes as -decode(complement) at any width — so a sample is
    corroboration, not proof.
    """
    fmt = mod.FORMATS[fmt_name]
    span = 1 << fmt.n
    msb = span >> 1
    step = max(1, span // samples)
    tested = fails = 0
    for raw in range(0, span, step):
        if raw in (0, msb):
            continue
        x = mod.decode(fmt, raw)
        y = mod.decode(fmt, (-raw) % span)
        if getattr(x, "kind", None) or getattr(y, "kind", None):
            continue
        tested += 1
        if Fraction(y) != -Fraction(x):
            fails += 1
    print(f"{fmt_name:<9} SAMPLED {tested:<7} negation: "
          f"{'HOLDS' if not fails else str(fails) + ' FAIL'}   (not exhaustive)")
    return fails


def main(argv) -> int:
    if not argv:
        print(__doc__)
        return 2
    mod = load_takum()
    total = 0
    for spec in argv:
        path, _, name = spec.partition(":")
        if not os.path.exists(path):
            print(f"{name}: dump {path} missing")
            return 2
        total += check(mod, name, path)

    print()
    for name in ("takum32", "takum64"):
        if name in mod.FORMATS:
            total += check_wide(mod, name)

    print()
    print("ALL CHECKS PASS" if total == 0 else f"{total} failures")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
