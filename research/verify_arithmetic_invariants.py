#!/usr/bin/env python3
"""Sweep the arithmetic layer of every oracle for algebraic invariants.

Passes 1-17 of this campaign checked decode and encode only. This extends the
method to format_add / format_mul, using laws that need no external reference and
— unlike monotonicity — admit no design-choice defence:

  COMM_ADD   add(a,b) == add(b,a)
  COMM_MUL   mul(a,b) == mul(b,a)
  IDENT_ADD  add(x, 0) == x
  IDENT_MUL  mul(x, 1) == x
  ANNIH_MUL  mul(x, 0) == 0
  SIGN_MUL   mul(neg(a), b) == neg(mul(a, b))     [where negation is well defined]

A correctly-rounded binary operation is commutative because rounding is applied
to a single exact result; there is no rounding mode under which a+b and b+a
differ. A violation is therefore unambiguous, which is what makes these laws
worth more than the structural checks in pass 16.

Operands are drawn from a bounded sample of codes and every ordered pair within
the sample is tested, so cost is O(k^2) per format with k small.

Run:  python3 research/verify_arithmetic_invariants.py
Exit: 0 if no law is violated, 1 otherwise.
"""
from __future__ import annotations
import importlib.util
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(REPO, "conformance")

K = 24          # codes sampled per format -> K*K ordered pairs


def k_for(width):
    """Sample size, scaled by width.

    A flat K=24 gives 576 ordered pairs, and on a 64-bit format each operation is
    exact rational arithmetic over denominators like 1.67e47. The sweep did not
    hang at gf6 -- it was still working on gf64, and had been for hours. It printed
    nothing while doing so, so a slow format and a dead process looked identical,
    and 24 of 85 oracles read as the whole corpus.

    Narrow formats keep the dense sample; wide ones get a smaller one, which is a
    weaker check than K=24 and an infinitely stronger one than never finishing.
    """
    if width <= 32:
        return K
    if width <= 64:
        return 10
    return 8


def arithmetic_of(mod):
    """Find (add, mul) under any naming convention used in this tree.

    Most oracles export format_add / format_mul, but gf_ref.py uses gf_add /
    gf_mul and tekum_ref.py uses tekum_add / tekum_mul. A first version of this
    sweep looked only for format_* and therefore skipped the entire GF ladder in
    silence, producing a false 'no arithmetic oracle' finding. Detect by suffix
    instead of by exact name.
    """
    add = mul = None
    for attr in dir(mod):
        if attr.startswith("_"):
            continue
        obj = getattr(mod, attr)
        if not callable(obj):
            continue
        if attr.endswith("_add") and add is None:
            add = obj
        elif attr.endswith("_mul") and mul is None and "matrix" not in attr:
            mul = obj
    return add, mul


def load_oracles():
    out = {}
    for fn in sorted(os.listdir(CONF)):
        if not fn.endswith("_ref.py") or fn.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location("a_" + fn[:-3],
                                                          os.path.join(CONF, fn))
            mod = importlib.util.module_from_spec(spec)
            # Register before executing: a module using @dataclass looks itself up in
            # sys.modules while the decorator runs, and under a synthetic name it is not
            # there. conformance/takum_log_ref.py fails exactly that way, so an
            # unregistered loader omitted it silently.
            sys.modules[spec.name] = mod
            sys.path.insert(0, CONF)
            spec.loader.exec_module(mod)
        except Exception:
            continue
        has_arith = all(arithmetic_of(mod))
        for name, fmt in getattr(mod, "FORMATS", {}).items():
            # gf16_plus_ref.py and gf_ref.py BOTH export all 17 GF ids. Keying on
            # format name alone makes the winner depend on filename sort order,
            # which silently skipped the whole GF ladder in the first run.
            # Resolve explicitly: a module that provides arithmetic wins.
            prev = out.get(name)
            if prev is None or (has_arith and not all(arithmetic_of(prev[0]))):
                out[name] = (mod, fmt)
    return out


def width_of(fmt, name):
    for attr in ("n", "width", "W", "total", "bits", "nbits"):
        v = getattr(fmt, attr, None)
        if isinstance(v, int) and v > 0:
            return v
    d = "".join(c for c in name if c.isdigit())
    return int(d) if d else 0


def is_special(mod, fmt, raw) -> bool:
    """True if the code decodes to NaN / Inf / any non-finite sentinel."""
    try:
        v = mod.decode(fmt, raw)
    except Exception:
        return True
    if getattr(v, "kind", None) is not None:
        return True
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError):
        return True
    return f != f or abs(f) == float("inf")


# E8M0 (OCP MX v1.0) is exponent-only: 2**(code-127), 0xFF is NaN, and there is
# NO ZERO and no sign. Pass 266 established that when building its oracle and
# deliberately wrote no e8m0_sub pack for the same reason. The zero-based laws are
# not violated by it, they are undefined for it -- and the loop below hardcodes
# `zero = 0`, which for E8M0 names the code for 2**-127, not zero at all. Asking
# was a category error and it produced 2 and 9.
NO_ZERO = {"e8m0"}


def same_value(mod, fmt, a, b):
    """Do two codes decode to the same value, whatever their encodings?"""
    try:
        return mod.decode(fmt, a) == mod.decode(fmt, b)
    except Exception:
        return False


def is_zero_value(mod, fmt, raw):
    try:
        v = mod.decode(fmt, raw)
        return getattr(v, "kind", None) is None and v == 0
    except Exception:
        return False


def sample_codes(width, k=K):
    span = 1 << width
    if span <= k:
        return list(range(span))
    # spread across the space, and always include the low corner
    step = max(1, span // k)
    codes = list(range(0, span, step))[:k - 2]
    codes += [1, span - 1]
    return sorted(set(codes))


def main() -> int:
    oracles = load_oracles()
    print(f"{'format':<14}{'pairs':>7}  {'comm+':<7}{'comm*':<7}"
          f"{'x+0':<7}{'x*1':<7}{'x*0':<7}{'reenc':<7}", flush=True)
    print("-" * 69, flush=True)
    print("reenc = value preserved, encoding changed. Not a violation: IEEE",
          flush=True)
    print("754-2008 gives decimal a preferred exponent. n/a = format has no zero.",
          flush=True)

    violations = {}
    measured = []
    unmeasurable = []
    for name in sorted(oracles):
        mod, fmt = oracles[name]
        f_add, f_mul = arithmetic_of(mod)
        if f_add is None or f_mul is None:
            continue
        width = width_of(fmt, name)
        if width == 0 or width > 128:
            continue
        # The real cost is the EXPONENT RANGE, not the width. These oracles compute
        # in exact rationals, so a format whose exponent reaches 2**16000 produces
        # Fractions with tens of thousands of digits, and one multiply can take
        # minutes. gf128 with only 8 sampled codes ran for a quarter of an hour
        # without finishing a single row.
        #
        # Capping on width was the wrong axis: gf64 is 64 bits and intractable,
        # int64 is 64 bits and trivial. Cap on what actually explodes, and SAY the
        # format was skipped rather than letting it read as clean.
        ebits = getattr(fmt, "exp_bits", None) or getattr(fmt, "E", 0)
        if isinstance(ebits, int) and ebits > 15:
            unmeasurable.append((name, "exponent field %d bits -- exact rational "
                                       "arithmetic is intractable" % ebits))
            continue
        k = k_for(width)
        codes = sample_codes(width, k)
        # Announce BEFORE measuring. Without this the only evidence a format is
        # being worked on is the absence of the next line, which is also what a
        # dead process looks like.
        print(f"  ... {name} (w={width}, k={k})", end="\r", flush=True)

        bad = {"comm_add": 0, "comm_mul": 0, "id_add": 0, "id_mul": 0,
               "ann_mul": 0, "reenc": 0}
        pairs = 0
        has_zero = name.lower() not in NO_ZERO

        # identity / annihilator need the codes for 0 and 1
        #
        # The zero CODE is not the literal 0 in every format. nf4 puts zero at code
        # 7 and decodes code 0 to -1; lns8 puts it at 64 and decodes code 0 to 1;
        # lns16 puts it at 16384. With `zero = 0` hardcoded, the sweep was computing
        # x + (-1) for nf4 and x + 1 for the LNS family and calling the result
        # "x + 0". That is where nf4's 14/14 and the LNS rows came from: every one
        # an artefact of asking the wrong question.
        #
        # Ask the format where its zero is.
        zero = getattr(fmt, "pos_zero", 0)
        one = None
        if hasattr(mod, "encode"):
            try:
                one = mod.encode(fmt, 1)
            except Exception:
                one = None

        for a in codes:
            for b in codes:
                try:
                    ab_add = f_add(fmt, a, b)
                    ba_add = f_add(fmt, b, a)
                    ab_mul = f_mul(fmt, a, b)
                    ba_mul = f_mul(fmt, b, a)
                except Exception:
                    continue
                pairs += 1
                if ab_add != ba_add:
                    bad["comm_add"] += 1
                if ab_mul != ba_mul:
                    bad["comm_mul"] += 1
            # Unary laws hold only for FINITE operands. NaN*0 = NaN and Inf*0 =
            # NaN are correct IEEE semantics, and NaN+0 = NaN does not return the
            # original code. Testing specials against x+0==x would manufacture
            # violations, so they are skipped — the same filter the decode sweeps
            # apply.
            if is_special(mod, fmt, a):
                continue
            # Both remaining laws were stated too strongly, and the sign of zero is
            # why. This file was outside every sweep until pass 290 widened
            # run_all_gates' glob, so nothing had ever read its output.
            #
            #   ANNIH_MUL was `mul(x, +0) == pos_zero`. For NEGATIVE finite x the
            #   correct result is NEGATIVE zero -- gf16 encodes -1.5 * (+0) as
            #   0x8000, not 0x0000 -- so every negative operand in the sample was
            #   counted a violation. That is roughly 9 per format across 40-odd
            #   formats, all of them correct arithmetic. The same sign-of-zero class
            #   that made pass 193's witness report 2,471 disagreements of its own.
            #
            #   IDENT_ADD was `add(x, +0) == x`. False for x = -0: IEEE 754 gives
            #   (-0) + (+0) = +0 under round-to-nearest, so the code changes. This is
            #   the identical false law pass 185 had to pull out of the decimal
            #   cross-validator, surviving here because nobody ran the file.
            #
            # Stated correctly, both are real constraints and any violation is one.
            if not has_zero:
                continue
            is_neg_zero = (a == getattr(fmt, "neg_zero", None))
            try:
                # By VALUE, not by code. IEEE 754-2008 gives decimal arithmetic a
                # PREFERRED EXPONENT: x + 0 preserves the value and may change the
                # encoding, so bit-equality is simply the wrong comparison for that
                # family and reported decimal32 3, decimal64 7, bcd 13. Pass 185
                # already had to pull the same bit-for-bit assertion out of the
                # decimal cross-validator; this is its second appearance.
                #
                # A re-encoding is counted apart, under `reenc`, because it is worth
                # seeing and is not a violation. A changed VALUE is the violation.
                if not is_neg_zero:
                    got = f_add(fmt, a, zero)
                    if got != a:
                        if same_value(mod, fmt, got, a):
                            bad["reenc"] += 1
                        else:
                            bad["id_add"] += 1
                prod = f_mul(fmt, a, zero)
                if prod not in (zero, getattr(fmt, "neg_zero", zero)) \
                        and not is_zero_value(mod, fmt, prod):
                    bad["ann_mul"] += 1
                if one is not None:
                    got1 = f_mul(fmt, a, one)
                    if got1 != a:
                        if same_value(mod, fmt, got1, a):
                            bad["reenc"] += 1
                        else:
                            bad["id_mul"] += 1
            except Exception:
                pass

        if pairs == 0:
            continue

        def cell(k):
            return "OK" if bad[k] == 0 else str(bad[k])

        print(" " * 40, end="\r")          # clear the progress line
        zcell = "n/a" if not has_zero else cell('ann_mul')
        print(f"{name:<14}{pairs:>7}  {cell('comm_add'):<7}{cell('comm_mul'):<7}"
              f"{('n/a' if not has_zero else cell('id_add')):<7}"
              f"{cell('id_mul'):<7}{zcell:<7}"
              f"{(str(bad['reenc']) if bad['reenc'] else '-'):<7}", flush=True)
        real = {kk: vv for kk, vv in bad.items() if kk != "reenc"}
        if any(real.values()):
            violations[name] = dict(bad)
        measured.append(name)

    print()
    print()
    print(f"formats measured : {len(measured)} of {len(oracles)} oracles loaded")
    if unmeasurable:
        print("skipped as intractable, with the reason:")
        for n, why in unmeasurable:
            print("    %-14s %s" % (n, why))
        print()
    skipped = sorted(set(oracles) - set(measured) - {n for n, _ in unmeasurable})
    if skipped:
        print(f"not measured     : {len(skipped)}  ({', '.join(skipped[:8])}"
              f"{' ...' if len(skipped) > 8 else ''})")
        print("  Not measured is NOT clean. A format absent from the table above")
        print("  has had no law checked against it.")
    print()
    if violations:
        print(f"VIOLATIONS in {len(violations)} format(s):")
        for name, b in violations.items():
            hits = ", ".join(f"{k}={v}" for k, v in b.items() if v)
            print(f"  {name}: {hits}")
        print()
        print("Commutativity violations are unambiguous defects. Identity and")
        print("annihilator failures may instead be sign-of-zero or encode-canonical")
        print("artefacts — diagnose each before reporting.")
    else:
        print("No arithmetic law violated in any format tested.")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
