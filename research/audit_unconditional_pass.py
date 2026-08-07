#!/usr/bin/env python3
"""Which scripts announce success with no way to fail?

conformance/gf_mx_ref.py printed

    ✓ GF-MX14 oracle: ALL TESTS PASS

unconditionally, after five sections of numbers and zero assertions. The oracle
could decode every code to zero and still print it. Pass 281 replaced that with a
self-test that can fail; this asks whether anything else in the corpus is doing
the same thing.

The question is not "does it print PASS". It is: **can this file's main path
report failure at all?** A file that announces success and has no mechanism to
announce anything else is not reporting a result, it is printing a constant.

WHAT COUNTS AS A WAY TO FAIL
----------------------------
Any of these, anywhere in the module:

    assert                     the ordinary form
    raise                      explicit, including a helper that raises
    sys.exit(x) / exit(x)      with a non-literal or non-zero argument
    return 1  (or any non-zero literal) from a top-level function

The last matters because this repo's own gates use an accumulator -- collect
findings, print them, `return 1 if fails else 0` -- and never assert once. That
pattern is fine and must not be flagged.

WHAT THIS CANNOT SEE
--------------------
That the assertions are the RIGHT ones, or that they cover anything. A file with
one vacuous assert passes this gate and would still be blind. That is what
research/audit_selftest_sensitivity.py is for -- it mutates the module and demands
the self-test notice. The two are complementary: this one finds files with no
brakes, that one finds brakes that are not connected to anything.

Usage:  python3 research/audit_unconditional_pass.py [--verbose]

Exits non-zero if a file announces success and cannot report failure.
"""
import ast
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIRS = ["conformance", "research", os.path.join("fpga", "witness")]

# An announcement that a CHECK SUCCEEDED. A bare check mark is not one: the first
# version flagged conformance/golden_ruler.py for printing "✓ RECOMMENDED: ...",
# which is a recommendation, not a verdict. Half the findings were false, in a gate
# about announcements that are not verdicts. The mark now only counts alongside a
# word that actually claims a pass.
CLAIM = re.compile(
    r"(\bALL\s+TESTS?\s+PASS\b|\bPASS(?:ED|ES)?\b|\bSUCCESS(?:FUL)?\b|"
    r"\bVERIFIED\b|\bCONFORMS?\b|[✓✔]\s*\w*\s*\b(?:PASS|OK|SUCCESS)\b)", re.I)

# "PASS/FAIL", "PASS or FAIL", "reports PASS/FAIL" -- describing an outcome space,
# not claiming one.
NEUTRAL = re.compile(r"PASS\s*[/|]\s*FAIL|FAIL\s*[/|]\s*PASS|PASS\s+or\s+FAIL", re.I)


def announces_success(tree):
    """Any string literal that claims success, reached from a print call."""
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "print"):
            continue
        for arg in ast.walk(node):
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if NEUTRAL.search(arg.value):
                    continue
                if CLAIM.search(arg.value):
                    return arg.value.strip()[:60]
    return None


def can_fail(tree):
    """Does any path exist that reports failure?"""
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assert, ast.Raise)):
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "exit":
                # sys.exit(main()) counts: the callee decides. sys.exit(0) does not.
                if not node.args:
                    continue
                a = node.args[0]
                if not (isinstance(a, ast.Constant) and a.value in (0, None)):
                    return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "exit" and node.args:
                a = node.args[0]
                if not (isinstance(a, ast.Constant) and a.value in (0, None)):
                    return True
        if isinstance(node, ast.Return) and node.value is not None:
            v = node.value
            if isinstance(v, ast.Constant) and isinstance(v.value, int) \
                    and not isinstance(v.value, bool) and v.value != 0:
                return True
            # `return 1 if fails else 0` -- the accumulator pattern this repo uses
            if isinstance(v, ast.IfExp):
                for side in (v.body, v.orelse):
                    if isinstance(side, ast.Constant) and side.value not in (0, None):
                        return True
    return False


def main():
    verbose = "--verbose" in sys.argv
    bad, checked, quiet = [], 0, 0
    for d in DIRS:
        for dp, dn, fn in os.walk(os.path.join(ROOT, d)):
            dn[:] = [x for x in dn if x not in
                     {"__pycache__", "vectors", ".gate_cache", "witness"}]
            for f in sorted(fn):
                if not f.endswith(".py") or f == os.path.basename(__file__):
                    continue
                p = os.path.join(dp, f)
                try:
                    tree = ast.parse(io.open(p, encoding="utf-8").read())
                except Exception:
                    continue
                checked += 1
                claim = announces_success(tree)
                if claim is None:
                    quiet += 1
                    continue
                if not can_fail(tree):
                    bad.append((os.path.relpath(p, ROOT), claim))

    print("Python files examined            : %d" % checked)
    print("  announce success somewhere     : %d" % (checked - quiet))
    print("  and CANNOT report failure      : %d" % len(bad))
    print()
    if bad:
        print("a printed success with no mechanism to print anything else:")
        for rel, claim in bad:
            print("    %-56s %s" % (rel, claim))
    else:
        print("every file that announces success can also announce failure.")
    print()
    print("This does not mean the assertions are right, or that they cover")
    print("anything -- one vacuous assert passes here. That is what")
    print("research/audit_selftest_sensitivity.py is for.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
