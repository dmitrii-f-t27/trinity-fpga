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
Every function the module publishes that a pack depends on: the encoder its arithmetic routes
through, `decode`, and each `*_add` / `*_mul`. One at a time, with the result perturbed. Every oracle here routes correctly-rounded values through
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

sys.path.insert(0, HERE)
import gate_cache                                                  # noqa: E402

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
    # Containers, before the scalar path. `r != 0` on a numpy array yields an array
    # and `if` on it raises, so every array-returning function fell through to the
    # field-bump branch, found no fields on an ndarray, and was returned UNCHANGED.
    # The gate then reported the self-test as surviving a mutation that never
    # happened -- gf_mx_ref's dequantize_block, quantize_tensor, mx_mul_matrix and
    # compute_quantization_error, four "insensitive" verdicts that were all false.
    # Exactly the trap pass 234 hit from the other direction, recorded in this
    # file's own docstring: the mutation was blind, not the module.
    try:
        import numpy as _np
        if isinstance(r, _np.ndarray):
            c = r.copy()
            if c.size:
                flat = c.reshape(-1)
                flat[0] = flat[0] + 1 if flat[0] == 0 else flat[0] * 2
            return c
    except Exception:
        pass
    if isinstance(r, dict):
        c = dict(r)
        for k, v in c.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            c[k] = v + 1 if v == 0 else v * 2
            return c
        return c
    if isinstance(r, (list, tuple)):
        seq = list(r)
        for i, v in enumerate(seq):
            if isinstance(v, bool):
                continue
            try:
                seq[i] = v + 1 if v == 0 else v * 2
                return type(r)(seq)
            except Exception:
                continue
        return r
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
    import re
    out = []
    enc = encoder_used(src)
    if f"\ndef {enc}(" in src:
        out.append(enc)
    if "\ndef decode(" in src:
        out.append("decode")
    # The arithmetic too. encode and decode are one code path each; format_add and
    # format_mul are where 2.4 million published vectors come from, and a self-test that
    # never checks a sum would pass a corrupted adder forever. The names are read from
    # the file rather than assumed, because gf_ref calls its pair gf_add / gf_mul and
    # tekum_ref uses tekum_add / tekum_mul.
    for m in re.finditer(r"^def (\w*_?(?:add|mul))\(", src, re.M):
        name = m.group(1)
        if not name.startswith("_"):
            out.append(name)
    if out:
        return out

    # Nothing matched the usual names. That does NOT mean there is nothing to
    # mutate -- gf16_plus_ref.py imports decode, encode and gf_mul from gf_ref and
    # defines none of them, so this returned empty and the oracle was reported as
    # "not assessed" for as long as this gate has existed. An oracle that has never
    # been tested for blindness is precisely what the gate is for, so a module that
    # names its functions differently must not be the one case it skips.
    #
    # Fall back to every public function the module DEFINES itself. Imported names
    # belong to the module they came from and are mutated when that module's turn
    # comes; underscore-prefixed helpers are excluded, since a self-test is not
    # obliged to pin private internals.
    #
    # Only a fallback. The 17 oracles already assessed keep exactly the targets
    # they had, so no existing verdict moves.
    for m in re.finditer(r"^def ([a-zA-Z]\w*)\(", src, re.M):
        out.append(m.group(1))
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
    """Case-insensitively, because it was not.

    This matched "SELF-TEST" and "self-test" exactly. conformance/gf_mx_ref.py says
    "Self-Test", so it was reported "no self-test" and skipped -- and behind that
    skip sat the only oracle in the corpus whose self-test asserted nothing at all
    and ended with an unconditional print of "ALL TESTS PASS". One capital letter
    kept the worst case out of the gate built to find it.
    """
    src = io.open(path, encoding="utf-8", errors="replace").read()
    return "__main__" in src and "self-test" in src.lower()


def run_mutated(path, original, fn):
    """Run the self-test with one function perturbed, WITHOUT touching the original.

    The first version wrote the mutation into the module and restored it in a finally
    block. Killing the run mid-flight left conformance/ieee_ref.py and
    conformance/posit_ref.py mutated on disk -- a gate that corrupts the corpus when
    interrupted is worse than no gate. This copies the whole conformance tree to a
    temporary directory, mutates the copy and runs there, so the originals are never
    opened for writing at all.
    """
    import shutil
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        dst = os.path.join(d, "conformance")
        shutil.copytree(CONF, dst,
                        ignore=shutil.ignore_patterns("vectors", "witness", "__pycache__"))
        target = os.path.join(dst, os.path.basename(path))
        io.open(target, "w", encoding="utf-8").write(inject(original, fn))
        return run_selftest(target, cwd=d)


def run_selftest(path, timeout=180, cwd=None):
    """(returncode, tail). A module with no self-test returns None.

    Bounded at three minutes per run. With five mutations per oracle across sixteen
    oracles the total matters, and a self-test that hangs under mutation is itself worth
    knowing about -- a timeout is reported as a failure, which is the right reading: the
    module noticed.
    """
    try:
        r = subprocess.run([sys.executable, path], capture_output=True, text=True,
                           cwd=cwd or ROOT, timeout=timeout)
    except subprocess.TimeoutExpired:
        class _R:
            returncode, stdout, stderr = 1, "", "timed out under mutation"
        r = _R()
    tail = (r.stdout or r.stderr).strip().split("\n")[-1][:70]
    return r.returncode, tail


def main() -> int:
    verbose = "--verbose" in sys.argv
    oracles = sorted(glob.glob(os.path.join(CONF, "*_ref.py")))
    # --only NAME narrows the sweep. With up to five mutations per oracle and sixteen
    # oracles the full run is long, and a partial answer that says which oracles it
    # covered beats a complete one nobody waits for.
    if "--only" in sys.argv:
        want = sys.argv[sys.argv.index("--only") + 1]
        oracles = [o for o in oracles if want in os.path.basename(o)]
    insensitive, sensitive, skipped = [], [], []

    # Sixteen oracles, up to five mutations each, a self-test run per mutation:
    # past run_all_gates.py's budget, so this timed out rather than ran. The
    # verdict for one oracle depends on its own bytes AND on every conformance
    # module its self-test imports, so the key covers that closure -- asked of the
    # interpreter, not inferred from `import` lines, because deferred and
    # conditional imports are exactly what a regex misses and a missed input is a
    # stale verdict wearing a green light. An oracle that will not import gets no
    # key and is never cached.
    cache = gate_cache.Cache("selftest_sensitivity",
                             enabled="--no-cache" not in sys.argv)
    pyver = "py%d.%d" % sys.version_info[:2]
    # THIS FILE is part of the key, and audit_yosys_reads' key deliberately is not.
    # The rule is: the key covers whatever determines the CACHED VALUE, not the
    # presentation around it.
    #
    #   here          the cached value is a verdict produced by targets() and the
    #                 mutation logic. Change either and the verdict can change, so
    #                 a stale entry would report the old gate's answer under the new
    #                 gate's name. Pass 280 changed targets() and would have done
    #                 exactly that.
    #
    #   yosys_reads   the cached value is yosys's own output for one file. Pass 278
    #                 rewrote how those strings are counted and could not have
    #                 changed one of them. Hashing that gate would invalidate 3,594
    #                 units for a cosmetic edit and teach everyone to pass
    #                 --no-cache, which is how a cache stops being used.
    mine = gate_cache.sha_files([os.path.abspath(__file__)])

    for path in oracles:
        base = os.path.basename(path)
        closure = gate_cache.python_imports_under(path, CONF)
        key = (gate_cache.sha_files(closure) + "|" + pyver + "|" + mine) if closure else None
        hit = cache.get(base, key)
        if hit is not None:
            v = hit["value"]
            {"sensitive": sensitive, "insensitive": insensitive,
             "skipped": skipped}[v["bucket"]].append(
                base if v["bucket"] == "sensitive" else (base, v["note"]))
            continue

        def record(bucket, note=""):
            cache.put(base, key, {"bucket": bucket, "note": note})

        if not has_selftest(path):
            skipped.append((base, "no self-test"))
            record("skipped", "no self-test")
            continue
        clean_rc, clean_tail = run_selftest(path)
        if clean_rc != 0:
            skipped.append((base, f"self-test already failing: {clean_tail}"))
            record("skipped", f"self-test already failing: {clean_tail}")
            continue

        original = io.open(path, encoding="utf-8").read()
        fns = targets(original)
        if not fns:
            skipped.append((base, "no encode or decode to mutate"))
            record("skipped", "no encode or decode to mutate")
            continue
        survived = []
        for fn in fns:
            rc, tail = run_mutated(path, original, fn)
            if rc == 0:
                survived.append((fn, tail))
        if survived:
            note = "; ".join(f"{fn} survives" for fn, _ in survived)
            insensitive.append((base, note))
            record("insensitive", note)
        else:
            sensitive.append(base)
            record("sensitive")
        if verbose:
            print(f"  {base:<20} clean rc=0, mutated rc={rc}")
    cache.save()
    print(cache.summary())

    print(f"oracles with a self-test              : "
          f"{len(sensitive) + len(insensitive)}")
    print(f"  fail on EVERY mutation              : {len(sensitive)}")
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
    rc, tail = run_mutated(target, before, encoder_used(before))
    restored = hash(io.open(target, encoding="utf-8").read()) == digest_before
    print(f"  with encode perturbed  -> rc {rc}  ({tail})")
    print(f"  original never written -> {restored}")

    ok = clean_rc == 0 and rc != 0 and restored
    print(f"\nself-check: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        raise SystemExit(self_check())
    raise SystemExit(main())
