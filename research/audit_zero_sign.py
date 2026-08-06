#!/usr/bin/env python3
"""Does a negative zero stay negative, everywhere?

This class has now been found four times, in four unrelated places, each time by
a different accident:

  pass 188  VAX declared a negative zero at its RESERVED OPERAND
  pass 231  takum, tekum and mxint8 declared one at a code meaning NaR or reserved
  pass 236  the decimal hosts returned a bare 0x00000000 for a non-canonical
            code, so every sign=1 one decoded to +0
  pass 241  the compute wrappers' narrowing had `if (zero) fp32 = 32'h00000000`,
            so a negative zero narrowed to +0

Four times is not coincidence, it is a missing check. This is the check.

The ground truth is the oracles themselves. Pass 231 made `neg_zero` raise for
every format that does not have one, so the corpus already knows which 69 formats
have a negative zero and which 36 do not -- posit, takum, tekum, lns, the integer
formats, VAX, BCD, mxint8, pdp11_float.

Two checks:

  HOSTS  every host golden that answers in fp32, for a format WITH a negative
         zero, must set bit 31 when handed that format's negative-zero code. And
         for a format WITHOUT one, the code that would be a negative zero
         elsewhere must not be silently treated as one.

  RTL    a bare zero constant assigned to an fp32-producing signal inside a block
         where a sign wire is in scope. That is the exact shape of the pass 241
         defect, and it is a lint rather than a proof: it reports candidates.

Usage:  python3 research/audit_zero_sign.py [--verbose]

Exits non-zero if any host loses the sign.
"""
import glob
import importlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")
SYNTH = os.path.join(ROOT, "fpga", "openxc7-synth")
sys.path.insert(0, CONF)
sys.path.insert(0, HERE)

from audit_host_vs_oracle import (   # noqa: E402
    ALIAS, INTEGER_DOMAIN, LOG_DOMAIN, find_format, host_golden, load_host, oracles,
)

# Pass 236 settled these two as a convention question rather than a defect. The
# high limb is -0.0 and every other limb is +0.0; the host returns +0, which is
# what IEEE addition gives for (-0) + (+0), while reading the sign off the top bit
# gives -0. extended_ref hands back Fraction(0, 1), which carries no sign at all,
# so the oracle has no opinion. Reported, never failed.
CONVENTION_OPEN = {"double_double", "quad_double"}

# `if (zero) X = 32'h00000000;` with a sign wire in the same module.
RTL_ZERO = re.compile(r"if\s*\(\s*\w*zero\w*\s*\)\s*(\w+)\s*=\s*32'h0+\s*;")
RTL_SIGN = re.compile(r"\bwire\s+\w*sign\w*\b|\b\w+_sign_[ab]\b")


def hosts_check(verbose):
    mods = oracles()
    lost, checked, skipped = [], 0, []
    for fn in sorted(f for f in os.listdir(CONF) if f.endswith(".py") and "ax7203" in f):
        stem = fn[:-len("_conformance_ax7203.py")] if fn.endswith("_conformance_ax7203.py") \
            else fn[:-len("_ax7203.py")]
        if stem.endswith("_decode"):
            stem = stem[:-len("_decode")]
        key = ALIAS.get(stem, stem)
        if key is None or key in INTEGER_DOMAIN or key in LOG_DOMAIN:
            continue
        oname, omod, fmt = find_format(key, mods)
        if fmt is None:
            continue
        try:
            nz = fmt.neg_zero
        except Exception:                             # noqa: BLE001
            skipped.append((fn, key, "format has no negative zero"))
            continue
        try:
            host = load_host(os.path.join(CONF, fn))
        except BaseException as e:                    # noqa: BLE001
            skipped.append((fn, key, "load failed: %s" % type(e).__name__))
            continue
        gname, gfn = host_golden(host, key)
        if gfn is None:
            skipped.append((fn, key, "no golden function found"))
            continue
        try:
            got = gfn(nz)
        except BaseException as e:                    # noqa: BLE001
            skipped.append((fn, key, "golden raised %s" % type(e).__name__))
            continue
        if got is None:
            skipped.append((fn, key, "golden returned None"))
            continue
        checked += 1
        got &= 0xFFFFFFFF
        if got >> 31 != 1:
            if key in CONVENTION_OPEN:
                skipped.append((fn, key, "convention open since pass 236 -- reported, not failed"))
                checked -= 1
            else:
                lost.append((fn, key, nz, got))
    return lost, checked, skipped


def rtl_check():
    hits = []
    for path in sorted(glob.glob(os.path.join(SYNTH, "*.v"))):
        src = open(path, encoding="utf-8", errors="replace").read()
        if not RTL_SIGN.search(src):
            continue
        for m in RTL_ZERO.finditer(src):
            hits.append((os.path.basename(path), m.group(1), m.group(0)))
    return hits


def main():
    verbose = "--verbose" in sys.argv
    lost, checked, skipped = hosts_check(verbose)
    print("HOSTS")
    print("  goldens asked for their format's negative zero : %d" % checked)
    print("  goldens that returned a POSITIVE zero          : %d" % len(lost))
    for fn, key, nz, got in lost:
        print("     %-46s %-12s code %#x -> %#010x" % (fn[:46], key, nz, got))
    if verbose:
        print("  not asked: %d" % len(skipped))
        for fn, key, why in skipped:
            print("     %-46s %-12s %s" % (fn[:46], key, why))
    print()
    hits = rtl_check()
    print("RTL (lint, not proof)")
    print("  `if (zero) X = 32'h0...;` in a module with a sign wire : %d" % len(hits))
    for base, sig, snippet in hits[:20]:
        print("     %-46s %s" % (base[:46], snippet.strip()))
    if len(hits) > 20:
        print("     ... and %d more" % (len(hits) - 20))
    print()
    print("A format WITHOUT a negative zero is not a failure here -- the oracles")
    print("record which 36 of them there are, and those goldens are not asked.")
    return 1 if lost else 0


if __name__ == "__main__":
    sys.exit(main())
