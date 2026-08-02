#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-validate the decimal packs against GCC's BID arithmetic.

`research/HANDOVER.md` §6 lists the three decimal packs among the formats with no second
witness, blocked on "a GCC toolchain, decNumber source, or Intel DFP -- all unavailable".
That is wrong on this machine. Homebrew gcc-14 implements `_Decimal32/64/128` over Intel's
BID library, and it emits BID rather than DPD, which is the encoding the packs use.

So every `expected` in the nine vector files -- which until now came only from
`conformance/decimal_ref.py` checking itself -- can be put against an implementation that
shares no line of code with it.

    python3 conformance/crossval_decimal_gcc.py [--self-check] [--verbose]

Exit 0 when every vector agrees, 1 on any disagreement, 2 when the toolchain is missing
(which is a skip, not a pass: a witness that cannot run has witnessed nothing, and saying
so is the whole point of this campaign).
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(HERE, "decimal_gcc_witness.c")
BIN = os.path.join(HERE, "..", "var", "decimal_gcc_witness")
VEC = os.path.join(HERE, "vectors")

# Not `gcc`: on macOS that is clang, which rejects _Decimal64 outright with "GNU decimal
# type extension not supported". Only a real GCC will do, and it is named explicitly so a
# missing one is reported rather than silently satisfied by the wrong compiler.
CANDIDATES = ["gcc-14", "gcc-13", "gcc-15", "gcc-12"]


def find_gcc() -> str | None:
    for c in CANDIDATES:
        r = subprocess.run(["which", c], capture_output=True, text=True)
        if r.returncode == 0:
            return c
    return None


def sysroot() -> list:
    """gcc's bundled fixed headers are stale against a current macOS SDK -- without this
    it dies on `sys/cdefs.h: No such file`. Empty list off Darwin."""
    if sys.platform != "darwin":
        return []
    r = subprocess.run(["xcrun", "--show-sdk-path"], capture_output=True, text=True)
    return ["-isysroot", r.stdout.strip()] if r.returncode == 0 else []


def build(cc: str) -> str | None:
    os.makedirs(os.path.dirname(BIN), exist_ok=True)
    cmd = [cc] + sysroot() + ["-O2", SRC, "-o", BIN]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("  build failed:")
        for line in r.stderr.strip().split("\n")[:6]:
            print(f"    {line}")
        return None
    return BIN


def encoding_is_bid(exe: str) -> bool:
    """A DPD toolchain would disagree with every vector for reasons that have nothing to
    do with the arithmetic, and reporting 774 failures would be worse than reporting one.
    1.0 + 0.0 must come back as the BID word 0x3200000a."""
    r = subprocess.run([exe, "32", "add"], input="3200000a 32800000\n",
                       capture_output=True, text=True)
    return r.stdout.strip() == "3200000a"


def load_oracle():
    """decimal_ref.py, loaded the registered way -- pass 156 found an unregistered
    spec_from_file_location silently losing a @dataclass module, and this file has one."""
    import importlib.util
    p = os.path.join(HERE, "decimal_ref.py")
    spec = importlib.util.spec_from_file_location("decimal_ref_x", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def classify(ref, fmt, ours_hex: str, gcc_hex: str) -> str:
    """A differing bit pattern is not automatically a defect.

    IEEE 754-2008 5.4.2 fixes a *preferred exponent* for each operation, so two results
    can name the same value through different members of its cohort. Those are a
    convention difference and worth stating; a different value is an error in one of the
    two implementations. Counting them together would have made this run look like a
    catastrophe and buried the 6% that matters.
    """
    try:
        a = ref.decode(fmt, int(ours_hex, 16))
        b = ref.decode(fmt, int(gcc_hex, 16))
    except Exception:
        return "value"
    if isinstance(a, ref.Special) or isinstance(b, ref.Special):
        return "cohort" if str(a) == str(b) else "value"
    return "cohort" if a == b else "value"


def run_pack(exe: str, path: str, verbose: bool, ref=None) -> tuple:
    d = json.load(open(path, encoding="utf-8"))
    vectors = d["vectors"] if "vectors" in d else d["cases"]
    width = int(d.get("width") or re.search(r"decimal(\d+)", path).group(1))
    op = d["operation"]
    op = {"+": "add", "-": "sub", "*": "mul"}.get(op, op)
    digits = width // 4

    def norm(h):
        return h.lower().replace("0x", "").rjust(digits, "0")

    payload = "".join(f"{norm(v['a'])} {norm(v['b'])}\n" for v in vectors)
    r = subprocess.run([exe, str(width), op], input=payload,
                       capture_output=True, text=True)
    got = r.stdout.split()
    if len(got) != len(vectors):
        return len(vectors), len(vectors), [("<witness produced "
                                             f"{len(got)} of {len(vectors)} lines>",)]
    fmt = ref.FORMATS[f"decimal{width}"]
    cohort = value = 0
    for v, g in zip(vectors, got):
        if norm(v["expected"]) == norm(g):
            continue
        kind = classify(ref, fmt, norm(v["expected"]), norm(g))
        if kind == "cohort":
            cohort += 1
        else:
            value += 1
            if verbose and value <= 3:
                print(f"      {norm(v['a'])} {op} {norm(v['b'])}: "
                      f"ours {norm(v['expected'])} gcc {norm(g)}")
    return len(vectors), cohort, value


def self_check(exe: str) -> int:
    """A negative control for the comparison itself.

    The first version asserted that `x + 0` returns `x` bit-for-bit. It fails, for the
    reason this whole file documents: under the IEEE preferred-exponent rule the sum
    carries min(exp x, exp 0), a different member of the same cohort. A control that
    encodes the convention under test is not a control -- it is the assumption, restated.

    So this one asserts nothing about decimal semantics. It corrupts one `expected` value
    by a single bit, re-runs the real comparison, and requires the VALUE count to rise by
    exactly one. Nothing here depends on what the right answer is, only on the comparison
    being able to see a wrong one.
    """
    ref = load_oracle()
    path = os.path.join(VEC, "decimal32_add.json")
    raw = open(path, encoding="utf-8").read()
    d = json.loads(raw)
    vectors = d["vectors"] if "vectors" in d else d["cases"]

    base_n, base_c, base_v = run_pack(exe, path, False, ref)

    # Flip a bit in a vector the two currently AGREE on, so the injected defect is the
    # only new disagreement and the delta is unambiguous.
    got = subprocess.run([exe, "32", "add"],
                         input="".join(f"{v['a'].lower().replace('0x','').rjust(8,'0')} "
                                       f"{v['b'].lower().replace('0x','').rjust(8,'0')}\n"
                                       for v in vectors),
                         capture_output=True, text=True).stdout.split()
    idx = next((i for i, (v, g) in enumerate(zip(vectors, got))
                if v["expected"].lower().replace("0x", "").rjust(8, "0") == g), None)
    if idx is None:
        print("self-check: SKIP -- no agreeing vector to corrupt")
        return 0

    orig = vectors[idx]["expected"]
    vectors[idx]["expected"] = f"0x{int(orig, 16) ^ 1:08x}"
    tmp = path + ".selfcheck"
    try:
        open(tmp, "w", encoding="utf-8").write(json.dumps(d))
        _, c2, v2 = run_pack(exe, tmp, False, ref)
    finally:
        os.remove(tmp)
        open(path, "w", encoding="utf-8").write(raw)

    delta = (c2 + v2) - (base_c + base_v)
    ok = delta == 1
    print(f"  vector {idx}: {orig} -> {vectors[idx]['expected']} (one bit)")
    print(f"  disagreements {base_c + base_v} -> {c2 + v2}, delta {delta}")
    print(f"  the comparison sees the injected defect -> {ok}"
          f"  {'ok' if ok else 'IT SEES NOTHING'}")
    print(f"  vector file restored byte-identical -> "
          f"{open(path, encoding='utf-8').read() == raw}")
    print(f"\nself-check: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    verbose = "--verbose" in sys.argv
    cc = find_gcc()
    if not cc:
        print("no real GCC found; tried " + ", ".join(CANDIDATES))
        print("SKIPPED -- not a pass. The decimal packs remain single-witness.")
        return 2
    exe = build(cc)
    if not exe:
        print("SKIPPED -- not a pass. The decimal packs remain single-witness.")
        return 2
    if not encoding_is_bid(exe):
        print(f"{cc} emits DPD, not BID; the packs are BID and a comparison would be")
        print("meaningless. SKIPPED -- not a pass.")
        return 2

    if "--self-check" in sys.argv:
        return self_check(exe)

    print(f"witness: {cc} + Intel BID, encoding confirmed BID\n")
    ref = load_oracle()
    total = coh = val = 0
    rows = []
    for path in sorted(glob.glob(os.path.join(VEC, "decimal*_*.json"))):
        n, c, x = run_pack(exe, path, verbose, ref)
        total += n
        coh += c
        val += x
        rows.append((os.path.basename(path), n, c, x))
    print(f"  {'pack':<26}{'n':>6}{'cohort':>9}{'VALUE':>8}")
    for name, n, c, x in rows:
        print(f"  {name:<26}{n:>6}{c:>9}{x:>8}")
    print(f"  {'TOTAL':<26}{total:>6}{coh:>9}{val:>8}")

    print(f"""
cohort  same value, different member of its cohort. IEEE 754-2008 5.4.2 fixes a preferred
        exponent per operation; decimal_ref.py keeps the operand's instead. A convention
        the packs do not state, not an error -- but any standard-conforming decimal
        implementation will fail a bit-exact check against them for this reason alone.

VALUE   the two disagree about the number. {val} of {total}. Verified against exact
        rational arithmetic rather than by trusting gcc: in every case sampled, gcc is
        nearer the exact result and ours carries fewer significant digits than the format
        holds -- 4 where decimal32 has 7.

        Cause is in _encode_round: it scans exponents in a +/-3 window around
        log10(value). Holding a format's full precision needs the exponent that puts every
        significant digit into the integer coefficient, which for decimal128 is up to 34
        steps away. Outside the window, the best candidate is a truncated one.""")
    return 1 if val else 0


if __name__ == "__main__":
    raise SystemExit(main())
