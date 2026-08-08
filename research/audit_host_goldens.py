#!/usr/bin/env python3
"""What does each hardware conformance host use as its golden?

Pass 232 found that conformance/compute_conformance_template.py scored the board
against a Python float32 proxy. That host is one of 107 `*_ax7203.py` hosts in
conformance/. The question this answers is whether it was alone.

A host's golden can come from four places, in descending order of trust:

  oracle   imports a conformance/*_ref.py module -- exact Fraction arithmetic
  pack     reads a conformance/vectors/*.json pack (which pass 232 made
           oracle-derived across the board)
  table    a literal list of expected values written into the host
  float    computes in Python float/float32 -- struct.pack('<f'), math.sqrt,
           or plain float arithmetic on decoded values

`float` is the category that matters: it is what pass 232 caught, and a host in
that category is scoring silicon against double-rounded, range-clamped values.

The classification is deliberately conservative. A host that imports an oracle
AND has a float path is reported as both, because importing an oracle does not
prove the golden comes from it.

Usage:  python3 research/audit_host_goldens.py
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")

ORACLE = re.compile(r"^\s*(?:from|import)\s+([a-z0-9_]+_ref)\b", re.M)
PACK = re.compile(r"vectors[/\\][\w*]+\.json|vectors_dir|VECTORS_DIR", re.I)

# The lossy step, and the only one worth flagging: a Python float being packed
# INTO the format's bits. That is what conformance/compute_conformance_template.py
# did -- decode to float32, compute, `struct.pack('<f', result)`, slice the bits.
#
# The first version of this check also flagged `float(`, `math.sqrt(`, `1.0 *` and
# `2.0 **`, and reported 38 hosts. It was wrong. corona_decode_host_ax7203.py, the
# most-cited host in the ledger, builds its golden as raw bit patterns --
# `(sign << 31) | (fe << 23) | fm` -- with no float arithmetic anywhere; it was
# flagged for the string "1.0" in a comment and a 2^(i/16) LUT. Constructing bits
# by shifting is exact. Only a float ROUND TRIP loses anything.
PACK_FLOAT = re.compile(r"struct\.pack\(\s*['\"][<>=!]?[fd]['\"]")
UNPACK_FLOAT = re.compile(r"struct\.unpack\(\s*['\"][<>=!]?[fd]['\"]")
SQRT = re.compile(r"\bmath\.sqrt\(")
GOLDEN_FN = re.compile(r"^\s*def\s+(\w*golden\w*|\w*expected\w*|\w*ref\w*)\s*\(", re.M)
UART = re.compile(r"HW RESULT")


def classify(src):
    kinds = set()
    if ORACLE.search(src):
        kinds.add("oracle")
    if PACK.search(src):
        kinds.add("pack")
    # A float golden needs a float to become bits again. unpack alone is a decode
    # for display; sqrt alone may be a self-test. pack('<f') is the lossy step.
    if PACK_FLOAT.search(src) or (UNPACK_FLOAT.search(src) and SQRT.search(src)):
        kinds.add("float")
    if not kinds and GOLDEN_FN.search(src):
        kinds.add("table")
    return kinds or {"unknown"}


def main():
    hosts = sorted(f for f in os.listdir(CONF)
                   if f.endswith(".py") and "ax7203" in f)
    if not hosts:
        print("no hosts found")
        return 1

    by_kind = collections.defaultdict(list)
    rows = []
    for fn in hosts:
        src = open(os.path.join(CONF, fn), encoding="utf-8", errors="replace").read()
        kinds = classify(src)
        oracles = sorted(set(ORACLE.findall(src)))
        drives_board = bool(UART.search(src)) or "serial" in src
        rows.append((fn, kinds, oracles, drives_board))
        for k in kinds:
            by_kind[k].append(fn)

    print("hardware conformance hosts (conformance/*ax7203*.py): %d" % len(hosts))
    print()
    for k in ("oracle", "pack", "table", "float", "unknown"):
        print("  %-8s %3d" % (k, len(by_kind[k])))
    print()

    suspect = [r for r in rows if "float" in r[1]]
    print("hosts whose golden path touches Python float: %d" % len(suspect))
    for fn, kinds, oracles, board in sorted(suspect):
        print("   %-52s %-22s %s"
              % (fn, "+".join(sorted(kinds)),
                 ("oracle: " + ",".join(oracles)) if oracles else "NO ORACLE IMPORT"))
    print()

    lonely = [r for r in rows if r[1] == {"float"}]
    print("hosts whose ONLY golden is a float path: %d" % len(lonely))
    for fn, _k, _o, board in sorted(lonely):
        print("   %-52s %s" % (fn, "drives the board" if board else ""))
    print()

    noboard = [r for r in rows if not r[3]]
    print("hosts that never open a serial port (not silicon evidence): %d" % len(noboard))
    for fn, _k, _o, _b in sorted(noboard)[:10]:
        print("   %s" % fn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
