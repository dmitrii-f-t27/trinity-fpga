#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Do the labelled constants in a .t27 spec mean what the label says?

The `.t27` specs are this project's declared single source of truth: the oracles, the
Verilog and the packs are all supposed to follow them. Nothing in this campaign had ever
checked a spec against itself.

Pass 197 went to `t27/specs/numeric/gf16.t27` to settle whether GoldenFloat widths other
than gf16 have infinities, and found something else on the way. The file carries a
32-entry table of the form

    pow2_table:
        .half 0x3C00   ; 2^0 = 1.0
        .half 0x3D00   ; 2^1 = 2.0
        .half 0x3D80   ; 2^2 = 4.0

Decoded as gf16 -- the format the same file declares, E=6, M=9, BIAS=31 -- those codes are
1/2, 3/4 and 7/8. Not powers of two, and not even a sequence. They are not binary16 either
(0x3C00 is 1.0 there, but 0x3D00 is 1.25). Every one of the eight entries checked
disagrees with its own label.

The table is **never referenced**. `pow2_table:` appears once in the file, as its own
definition. Dead data in the source of truth is how a table gets to be wrong for as long
as this one has, and dead is not the same as harmless: anyone implementing from the spec
reads it as authoritative.

    python3 research/audit_spec_constants.py [--verbose] [--self-check]

WHAT IT CHECKS
--------------
Any `.half`/`.word` line carrying a `; <expr> = <value>` comment is a claim: this code
denotes this value in this format. The checker decodes the code with the format the spec
declares and compares. It reports only lines that carry such a label -- an unlabelled
constant makes no claim and is not the checker's business.

The format is read from the spec's own `.const BIAS`, `EXP_BITS` and `MANT_BITS` where
present, and from `gf_ref.FORMATS` where the spec omits them. Where neither is available
the file is reported as unchecked rather than skipped silently.
"""
from __future__ import annotations

import glob
import importlib
import os
import re
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SPEC_DIRS = [os.path.join(ROOT, "t27", "specs", "numeric"),
             os.path.join(ROOT, "specs", "numeric")]

LABELLED = re.compile(
    r"^\s*\.(?:half|word|byte)\s+(0[xX][0-9A-Fa-f]+)\s*;\s*(.+?)\s*=\s*([-\d.eE+]+)\s*$")
# Two spellings appear: `.const BIAS 31` and `const EXP_BITS : u8 = 3`. The first version
# of this pattern used `\w*` between the name and the number, which is greedy and ate the
# leading digits -- `.const BIAS 31` parsed as BIAS = 1, and the self-check missed it
# because the control read the bias from gf_ref rather than from the parser it was meant
# to be testing. The alternation below is explicit about both forms and matches no third.
CONST = re.compile(
    r"^\s*\.?const\s+([A-Z_][A-Z0-9_]*)\s*"
    r"(?::\s*\w+\s*)?"          # optional `: u8`
    r"(?:=\s*)?"                 # optional `=`
    r"(\d+)\b", re.M)


def spec_format(path, gf):
    """(exp_bits, mant_bits, bias) from the spec, falling back to gf_ref by file name."""
    text = open(path, encoding="utf-8", errors="replace").read()
    consts = {m.group(1): int(m.group(2)) for m in CONST.finditer(text)}
    e = consts.get("EXP_BITS")
    m = consts.get("MANT_BITS")
    b = consts.get("BIAS", consts.get("EXP_BIAS"))
    name = os.path.basename(path)[:-4]
    if (e is None or m is None or b is None) and name in gf.FORMATS:
        f = gf.FORMATS[name]
        e = e if e is not None else f.exp_bits
        m = m if m is not None else f.mant_bits
        b = b if b is not None else f.bias
    if None in (e, m, b):
        return None
    return e, m, b


def decode(code, e, m, b):
    sign = (code >> (e + m)) & 1
    exp = (code >> m) & ((1 << e) - 1)
    mant = code & ((1 << m) - 1)
    if exp == 0:
        v = Fraction(mant, 1 << m) * Fraction(2) ** (1 - b)
    else:
        v = (1 + Fraction(mant, 1 << m)) * Fraction(2) ** (exp - b)
    return -v if sign else v


def main() -> int:
    verbose = "--verbose" in sys.argv
    sys.path.insert(0, os.path.join(ROOT, "conformance"))
    gf = importlib.import_module("gf_ref")

    files = []
    for d in SPEC_DIRS:
        files += sorted(glob.glob(os.path.join(d, "*.t27")))

    rows, unchecked = [], []
    for path in files:
        fmt = spec_format(path, gf)
        text = open(path, encoding="utf-8", errors="replace").read()
        labels = [(int(mm.group(1), 16), mm.group(2), mm.group(3))
                  for line in text.splitlines()
                  for mm in [LABELLED.match(line)] if mm]
        if not labels:
            continue
        if fmt is None:
            unchecked.append((os.path.basename(path), len(labels)))
            continue
        e, m, b = fmt
        wrong = []
        for code, expr, val in labels:
            got = decode(code, e, m, b)
            try:
                want = Fraction(val)
            except (ValueError, ZeroDivisionError):
                continue
            if got != want:
                wrong.append((code, expr, val, got))
        rows.append((os.path.basename(path), (e, m, b), len(labels), wrong))

    total = sum(r[2] for r in rows)
    bad = sum(len(r[3]) for r in rows)
    print(f"specs with labelled constants        : {len(rows)}")
    print(f"  labelled constants checked         : {total}")
    print(f"  DISAGREE with their own label      : {bad}")
    print(f"  specs whose format could not be read : {len(unchecked)}\n")

    for name, (e, m, b), n, wrong in rows:
        flag = "ok" if not wrong else f"{len(wrong)} of {n} WRONG"
        print(f"  {name:<22} E={e} M={m} BIAS={b}   {flag}")
        for code, expr, val, got in (wrong if verbose else wrong[:3]):
            print(f"      {code:#06x} labelled {expr} = {val}, decodes to {got}")
        if wrong and not verbose and len(wrong) > 3:
            print(f"      ... and {len(wrong) - 3} more")

    for name, n in unchecked:
        print(f"  {name:<22} {n} labelled constants, FORMAT UNREADABLE -- not checked")

    print("""
A labelled constant is a claim: this code denotes this value in this format. An unlabelled
one makes no claim and is not checked here.

The specs are this project's declared source of truth, and nothing had ever checked one
against itself. gf16.t27's pow2_table is never referenced anywhere in the file -- dead data
is how a table stays wrong this long, and dead is not harmless, because anyone implementing
from the spec reads it as authoritative.""")
    return 1 if bad else 0


def self_check() -> int:
    """The decoder used here must agree with the oracle on codes whose value is not in
    dispute, or every disagreement it reports is about itself. Then a deliberately
    mislabelled line must be caught."""
    sys.path.insert(0, os.path.join(ROOT, "conformance"))
    gf = importlib.import_module("gf_ref")
    f = gf.FORMATS["gf16"]
    e, m, b = f.exp_bits, f.mant_bits, f.bias

    n = ok = 0
    for code in range(0, 1 << 16, 37):
        a = gf.decode(f, code)
        if isinstance(a, gf.Special):
            continue
        n += 1
        ok += decode(code, e, m, b) == a
    agree = ok == n
    print(f"  this file's decoder vs gf_ref on gf16: {ok}/{n} -> {agree}")

    # The PARSER, not just the decoder. gf16.t27 declares BIAS 31; anything else means the
    # constant regex is reading the file wrong, which is how the first version reported
    # every entry as wrong for the wrong reason.
    parsed = spec_format(os.path.join(ROOT, "t27", "specs", "numeric", "gf16.t27"), gf)
    parse_ok = parsed == (e, m, b)
    print(f"  gf16.t27 parses as E,M,BIAS = {parsed}, gf_ref says {(e, m, b)} "
          f"-> {parse_ok}")

    one = (b << m)
    good = decode(one, e, m, b) == 1
    print(f"  {one:#06x} really is 1.0 in gf16 -> {good}")
    caught = decode(0x3C00, e, m, b) != 1
    print(f"  and the spec's 0x3C00 labelled 1.0 is not -> {caught} "
          f"(it decodes to {decode(0x3C00, e, m, b)})")

    passed = agree and good and caught and parse_ok
    print(f"\nself-check: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        raise SystemExit(self_check())
    raise SystemExit(main())
