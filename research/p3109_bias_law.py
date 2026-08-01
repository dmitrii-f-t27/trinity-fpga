#!/usr/bin/env python3
"""Does P3109 use bias = 2^(e-1) at every width, or only the four already checked?

Passes 64-65 compared four (K,P) configurations against the in-tree oracles and
found one uniform ratio of 2, implying P3109's bias is exactly one greater than
IEEE 754's at those points. Four points is a hypothesis. The tree holds 504 tables.

Downloading 154 MB to check a bias would be absurd. The bias is recoverable from a
SINGLE row -- the smallest positive subnormal, codepoint 0x1:

    value(0x1) = 2^(2 - bias - P)      =>      bias = 2 - P - log2(value)

so an HTTP range request for the first few hundred bytes of each file settles it.
Verified against the four already measured:

    K8P4   0x0.4p-8    = 2^-10   -> bias = 2 - 4  + 10  = 8    (IEEE 7)
    K8P3   0x0.8p-16   = 2^-17   -> bias = 2 - 3  + 17  = 16   (IEEE 15)
    K16P11 0x0.8p-24   = 2^-25   -> bias = 2 - 11 + 25  = 16   (IEEE 15)
    K16P8  0x0.4p-132  = 2^-134  -> bias = 2 - 8  + 134 = 128  (IEEE 127)

Run:  python3 research/p3109_bias_law.py
Exit: 0 if bias = 2^(e-1) holds everywhere it could be read, 1 if any width breaks it.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from fractions import Fraction

# The tree API returns the FULL path, "Value Tables/Hexadecimal/K8/...", so the
# base must stop at main/. A first version repeated the prefix here and produced
# .../Value%20Tables/Hexadecimal/Value%20Tables/... -- 238 files "unreadable",
# which looked like a property of the data and was a typo in one string.
RAW = "https://raw.githubusercontent.com/P3109/Public/main/{path}"


def hexfloat_log2(s: str):
    """log2 of a hex float that is an exact power of two, else None."""
    low = s.strip().lower().lstrip("+-")
    if not low.startswith("0x"):
        return None
    mant, _, exp = low[2:].partition("p")
    e = int(exp) if exp else 0
    whole, _, frac = mant.partition(".")
    v = Fraction(int(whole or "0", 16))
    if frac:
        v += Fraction(int(frac, 16), 16 ** len(frac))
    if v == 0:
        return None
    v *= Fraction(2) ** e
    n, d = v.numerator, v.denominator
    if n & (n - 1) or d & (d - 1):          # not a power of two
        return None
    return n.bit_length() - d.bit_length()


def list_tables() -> list[str]:
    out = subprocess.check_output(
        ["gh", "api", "repos/P3109/Public/git/trees/main?recursive=1",
         "--jq", '[.tree[] | select(.type=="blob") | .path] | .[]'], text=True)
    keep = []
    for p in out.splitlines():
        if not p.endswith(".csv") or "Value Tables" not in p:
            continue
        if "/signed/" not in p:              # unsigned has no sign bit; different law
            continue
        keep.append(p)
    return keep


def head(path: str, nbytes: int = 400) -> str:
    url = RAW.format(path=path.replace(" ", "%20"))
    try:
        return subprocess.check_output(
            ["curl", "-sSL", "--max-time", "60", "-r", f"0-{nbytes}", url],
            text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return ""


def main() -> int:
    tables = list_tables()
    print(f"signed value tables in the tree: {len(tables)}\n")

    ok = broken = unread = 0
    breaks = []
    seen: dict[tuple[int, int], int] = {}

    for path in tables:
        m = re.search(r"/K(\d+)/P(\d+)/", path)
        if not m:
            continue
        K, P = int(m.group(1)), int(m.group(2))
        e = K - P
        if e < 1:
            continue                          # no exponent field to bias

        if (K, P) in seen:                    # se and sf share a bias
            continue

        text = head(path)
        row = None
        for line in text.splitlines()[1:]:
            parts = line.split(",")
            if len(parts) < 2:
                continue
            # Compare the codepoint by VALUE, not by spelling. Wider formats
            # zero-pad -- K16 writes 0x0001 -- so a string test for "0x1" or
            # "0x01" silently skipped 184 of 211 configurations and reported them
            # as unreadable data.
            try:
                cp = int(parts[0].strip(), 16)
            except ValueError:
                continue
            if cp == 1:
                row = parts[1].strip()
                break
        if row is None:
            unread += 1
            continue

        lg = hexfloat_log2(row)
        if lg is None:
            unread += 1
            continue

        bias = 2 - P - lg
        expect = 2 ** (e - 1)
        seen[(K, P)] = bias
        if bias == expect:
            ok += 1
        else:
            broken += 1
            breaks.append((K, P, e, bias, expect, row))

    print(f"configurations read : {len(seen)}")
    print(f"  bias = 2^(e-1)    : {ok}")
    print(f"  DIFFERENT         : {broken}")
    print(f"  unreadable        : {unread}")

    for K, P, e, got, want, row in breaks[:12]:
        print(f"    K{K}P{P}  e={e}  bias={got} but 2^(e-1)={want}   (0x1 -> {row})")

    print()
    if broken == 0 and ok:
        print(f"P3109 uses bias = 2^(e-1) at every one of the {ok} configurations")
        print("readable here, against IEEE 754's 2^(e-1) - 1. The four-point result")
        print("of passes 64-65 generalises to the family: every P3109 binaryKpP")
        print("value is exactly twice its same-layout IEEE/OCP counterpart.")
    elif broken:
        print(f"{broken} configuration(s) do NOT follow 2^(e-1). The rule is not")
        print("uniform, and the cross-walk claim has to be stated per width.")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
