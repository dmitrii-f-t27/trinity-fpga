#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Would each oracle's self-test notice if the oracle changed?

A self-test that asserts what the code happens to do passes forever, including after the
code becomes wrong. This campaign has hit that five times, each time in a check written by
the same hand:

    pass 185   `x + 0 == x` bit-for-bit, in the decimal cross-validator's control. False
               under the IEEE preferred-exponent rule -- the very convention being tested.
    pass 188   audit_expansion_canonicality asserted that no operand is non-canonical.
               Pass 188 made that false on purpose and the check went red at an
               improvement.
    pass 193   the GoldenFloat arithmetic witness dropped the sign of zero and reported
               2,471 disagreements that were its own.
    pass 200   audit_rtl_special_widths labelled every numeric agreement "flag only",
               which stopped being true the moment the fix landed.
    pass 214   mxfp_ref's own self-test asserted `1+1=2` for MXINT8, unrepresentable once
               the format's implied binary point was applied correctly.

The shape is always the same: an assertion true of the implementation rather than of the
format. It cannot be found by reading, because reading is what produced it.

It can be found by mutation. Perturb the module and require the self-test to fail.

    python3 research/audit_selftest_sensitivity.py [--verbose] [--self-check]

WHAT IS MUTATED
---------------
The encode-like function the module's own `format_add` routes through -- `encode` for most,
`encode_from_log` for lns_ref -- with one bit flipped in its result. Every oracle here routes correctly-rounded values through
encode, so a one-bit change to what it returns is the smallest edit that makes the module
observably wrong without making it crash. A self-test that still passes is asserting
something other than the module's behaviour.

WHAT A PASS HERE DOES NOT MEAN
------------------------------
Only that the self-test is sensitive to THIS mutation. It does not mean the test is
complete, that its assertions are the right ones, or that a differently-wrong module would
be caught. Mutation testing bounds a check from below and never from above.
"""
from __future__ import annotations

import glob
import importlib
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")

MUTATION = '''
# --- injected by research/audit_selftest_sensitivity.py; removed after the run ---
_orig_{fn} = {fn}


def {fn}(*a, **k):                 # noqa: F811
    r = _orig_{fn}(*a, **k)
    # Type-aware, because a decoder does not return an int. The first version flipped a
    # bit only when the result was an int, so mutating decode -- which returns a Fraction
    # or a Special -- was a no-op, and all sixteen oracles looked blind to it. They are
    # not; the mutation was.
    if isinstance(r, bool):
        return r
    if isinstance(r, int):
        return r ^ 1
    try:
        return r * 2 if r != 0 else r.__class__(1)
    except Exception:
        pass
    # Objects that do not multiply -- gfternary's PhiVal(a, b) is one. Bump the first
    # numeric field. Without this the mutation silently returned the value unchanged and
    # the module looked blind to a corrupted decode when it was the gate that was blind.
    fields = (getattr(type(r), "__slots__", None)
              or tuple(getattr(type(r), "__dataclass_fields__", ()))
              or tuple(vars(r)) if hasattr(r, "__dict__") else ())
    for attr in fields or ():
        try:
            v = getattr(r, attr)
            if isinstance(v, bool) or not hasattr(v, "__add__"):
                continue
            import copy
            c = copy.copy(r)
            object.__setattr__(c, attr, v + 1)
            return c
        except Exception:
            continue
    return r
'''


def targets(src):
    """Every function worth perturbing: the encoder the arithmetic uses, and decode.

    The first version mutated only the encoder. Half this corpus is decode packs, and a
    self-test that never checks what decode returns would pass a corrupted decoder
    forever -- the same blind spot in the other direction. Both are tried, and a module
    is sensitive only if BOTH mutations are caught.
    """
    out = []
    enc = encoder_used(src)
    if f"\ndef {enc}(" in src:
        out.append(enc)
    if "\ndef decode(" in src:
        out.append("decode")
    return out


def encoder_used(src):
    """Which encode-like function the module's ARITHMETIC routes through.

    Mutating `encode` marked lns_ref insensitive, and it is not: its format_add and
    format_mul go through `encode_from_log`, so perturbing `encode` changed nothing the
    self-test could see. That was a limit of this gate, not a defect in the module.

    The name is read from format_add's own source rather than assumed, which is the same
    discipline pass 191 had to learn when a hardcoded `format_add` wrote off 54 packs.
    """
    import re
    m = re.search(r"^def format_add\(.*?(?=^def |\Z)", src, re.S | re.M)
    body = m.group(0) if m else src
    for name in ("encode_from_log", "encode"):
        if re.search(rf"\b{name}\(", body):
            return name
    return "encode"


def inject(src, fn="encode"):
    """Put the mutation BEFORE the `if __name__` block.

    Appending it to the end does nothing: the guard runs the self-test and exits before
    the override is ever defined, so every module looks insensitive. The control caught
    that on its first run, which is the whole reason it asks for a clean pass and a
    mutated failure rather than just the second.
    """
    idx = src.rfind("\nif __name__ ==")
    if idx == -1:
        return src + MUTATION.format(fn=fn)
    return src[:idx] + "\n" + MUTATION.format(fn=fn) + src[idx:]


def has_selftest(path):
    src = io.open(path, encoding="utf-8", errors="replace").read()
    return "__main__" in src and ("SELF-TEST" in src or "self-test" in src)


def run_selftest(path):
    """(returncode, tail). A module with no self-test returns None."""
    r = subprocess.run([sys.executable, path], capture_output=True, text=True,
                       cwd=ROOT, timeout=600)
    tail = (r.stdout or r.stderr).strip().split("\n")[-1][:70]
    return r.returncode, tail


def main() -> int:
    verbose = "--verbose" in sys.argv
    oracles = sorted(glob.glob(os.path.join(CONF, "*_ref.py")))
    insensitive, sensitive, skipped = [], [], []

    for path in oracles:
        base = os.path.basename(path)
        if not has_selftest(path):
            skipped.append((base, "no self-test"))
            continue
        clean_rc, clean_tail = run_selftest(path)
        if clean_rc != 0:
            skipped.append((base, f"self-test already failing: {clean_tail}"))
            continue

        original = io.open(path, encoding="utf-8").read()
        fns = targets(original)
        if not fns:
            skipped.append((base, "no encode or decode to mutate"))
            continue
        survived = []
        for fn in fns:
            try:
                io.open(path, "w", encoding="utf-8").write(inject(original, fn))
                rc, tail = run_selftest(path)
            finally:
                io.open(path, "w", encoding="utf-8").write(original)
            if rc == 0:
                survived.append((fn, tail))
        if survived:
            insensitive.append((base, "; ".join(f"{fn} survives" for fn, _ in survived)))
        else:
            sensitive.append(base)
        if verbose:
            print(f"  {base:<20} clean rc=0, mutated rc={rc}")

    print(f"oracles with a self-test              : "
          f"{len(sensitive) + len(insensitive)}")
    print(f"  fail when encode AND decode perturbed: {len(sensitive)}")
    print(f"  survive at least one mutation       : {len(insensitive)}")
    print(f"  not assessed                        : {len(skipped)}\n")

    for base, tail in insensitive:
        print(f"  INSENSITIVE  {base}")
        print(f"      still reports: {tail}")
    for base, why in skipped:
        print(f"  skipped      {base}: {why}")

    print("""
A self-test that survives a one-bit change to encode is asserting something other than the
module's behaviour. That is how `1+1=2` for MXINT8 survived a wrong implied binary point,
and how `x + 0 == x` survived the IEEE preferred-exponent rule.

Passing here means only that the test is sensitive to THIS mutation. It does not mean the
test is complete, that its assertions are the right ones, or that a differently-wrong
module would be caught. Mutation bounds a check from below, never from above.""")
    return 1 if insensitive else 0


def self_check() -> int:
    """The mutation must actually break something, and the file must come back unchanged.
    Both matter: a mutation that does nothing would mark every test insensitive, and a
    restore that fails would leave the corpus corrupted."""
    target = os.path.join(CONF, "gf_ref.py")
    if not os.path.exists(target):
        print("gf_ref.py absent")
        return 1
    before = io.open(target, encoding="utf-8").read()
    digest_before = hash(before)

    clean_rc, _ = run_selftest(target)
    print(f"  gf_ref self-test clean -> rc {clean_rc}")
    try:
        io.open(target, "w", encoding="utf-8").write(inject(before, encoder_used(before)))
        rc, tail = run_selftest(target)
    finally:
        io.open(target, "w", encoding="utf-8").write(before)

    restored = hash(io.open(target, encoding="utf-8").read()) == digest_before
    print(f"  with encode perturbed  -> rc {rc}  ({tail})")
    print(f"  file restored byte-identical -> {restored}")

    ok = clean_rc == 0 and rc != 0 and restored
    print(f"\nself-check: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        raise SystemExit(self_check())
    raise SystemExit(main())
