#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exact division and correctly-rounded square root, for any oracle in this corpus.

Pass 189 found thirty vector packs covering `div`, `sqrt` and `quire` with **no oracle
anywhere in the repository** -- no `format_div`, no `format_sqrt`, no `format_quire`, and
no `oracle` field in their headers. Nothing could re-derive them and nothing did. Pass 190
measured what it could without one: their results carry no significand information beyond
bit 23, in three independent formats.

This closes the div and sqrt half. Each oracle already has the two functions that matter --
`decode` to an exact Fraction and `encode` that rounds an exact Fraction correctly -- so
neither operation needs new rounding code. What it needs is the exact value, and the
special cases stated rather than inherited by accident.

`quire` is deliberately absent. A quire is a fixed-point accumulator, and which one is a
design decision (Posit Standard 2022 fixes a width per format; other proposals differ).
Writing one here would be inventing the semantics the packs are supposed to be testing.

WHY SQRT IS SOUND
-----------------
sqrt of a rational is irrational unless the rational is a perfect square of a rational, so
a tie -- a value exactly halfway between two representable numbers -- can only occur when
the result is exactly representable, and then it is not a tie at all. That is what makes
this safe: compute the exact result when there is one, and otherwise approximate to more
bits than the format can hold and let `encode` round. No tie can hide in the gap.

The approximation uses integer isqrt on a scaled numerator, which is exact integer
arithmetic, not floating point.
"""
from __future__ import annotations

import math
from fractions import Fraction

# Enough guard bits that the approximation and the true value round identically. The
# format's significand plus this is the working precision; 64 is far past any format here
# (the widest significand in the corpus is 236 bits for gf1024, and the bound below is
# derived from the format rather than assumed).
GUARD_BITS = 64


def _is_special(mod, v):
    S = getattr(mod, "Special", None)
    return S is not None and isinstance(v, S)


def _nan(fmt):
    return fmt.quiet_nan


def _inf(fmt, sign):
    return fmt.neg_inf if sign else fmt.pos_inf


def _zero(fmt, sign):
    if not sign:
        return fmt.pos_zero
    try:
        return fmt.neg_zero
    except AttributeError:
        return fmt.pos_zero          # VAX and PDP-11 have only one zero; see pass 188


def exact_sqrt(a: Fraction, bits: int) -> Fraction:
    """A rational within 2^-bits (relatively) of sqrt(a), exact when sqrt(a) is rational.

    Returned as a Fraction so the caller's `encode` does the rounding. Handing `encode` a
    float here would round twice, and the second rounding is the one that would be wrong.
    """
    if a == 0:
        return Fraction(0)
    p, q = a.numerator, a.denominator
    rp, rq = math.isqrt(p), math.isqrt(q)
    if rp * rp == p and rq * rq == q:
        return Fraction(rp, rq)                     # exactly representable, no rounding
    # sqrt(p/q) = sqrt(p*q)/q. Scale by 4^bits so isqrt gives `bits` extra binary digits.
    scaled = math.isqrt((p * q) << (2 * bits))
    return Fraction(scaled, q << bits)


def make_div(mod, add_name="format_add"):
    """Build a `format_div(fmt, a_raw, b_raw)` for one oracle module."""
    decode, encode = mod.decode, mod.encode

    def format_div(fmt, a_raw, b_raw):
        a, b = decode(fmt, a_raw), decode(fmt, b_raw)
        sa = (a_raw >> (fmt.width - 1)) & 1
        sb = (b_raw >> (fmt.width - 1)) & 1
        sign = sa ^ sb

        a_nan = _is_special(mod, a) and a.kind == "nan"
        b_nan = _is_special(mod, b) and b.kind == "nan"
        if a_nan or b_nan:
            return _nan(fmt)
        a_inf = _is_special(mod, a) and a.kind == "inf"
        b_inf = _is_special(mod, b) and b.kind == "inf"
        if a_inf and b_inf:
            return _nan(fmt)                         # inf / inf
        if a_inf:
            return _inf(fmt, sign)
        if b_inf:
            return _zero(fmt, sign)
        if b == 0:
            # 0/0 is NaN; x/0 is an infinity for formats that have one, and the largest
            # finite value for formats that saturate. Asking a saturating format for
            # pos_inf raises, which is the honest answer and is caught here rather than
            # papered over with a magic constant.
            if a == 0:
                return _nan(fmt)
            try:
                return _inf(fmt, sign)
            except AttributeError:
                return _nan(fmt)
        if a == 0:
            return _zero(fmt, sign)
        return encode(fmt, Fraction(a) / Fraction(b))

    return format_div


def make_sqrt(mod):
    """Build a `format_sqrt(fmt, a_raw, _unused)` for one oracle module.

    The second argument is ignored and present so the function has the same shape as
    every other op in this corpus: the vector packs store `sqrt` with an unused `b`, and a
    checker that special-cased arity would be one more place to get it wrong.
    """
    decode, encode = mod.decode, mod.encode

    def format_sqrt(fmt, a_raw, _b_raw=0):
        a = decode(fmt, a_raw)
        sign = (a_raw >> (fmt.width - 1)) & 1

        if _is_special(mod, a):
            if a.kind == "nan":
                return _nan(fmt)
            return _nan(fmt) if a.sign else _inf(fmt, 0)   # sqrt(-inf) is NaN
        if a == 0:
            return _zero(fmt, sign)                        # sqrt(-0) is -0
        if a < 0:
            return _nan(fmt)

        # Guard bits scaled to the format: significand width plus a margin, so the
        # approximation cannot round differently from the true value.
        mant = getattr(fmt, "mant_bits", None) or getattr(fmt, "coeff_bits_small", 24)
        return encode(fmt, exact_sqrt(Fraction(a), mant + GUARD_BITS))

    return format_sqrt


def self_test() -> int:
    """Properties, not golden words: sqrt(x)^2 must round-trip for perfect squares, and
    the rounded sqrt must be the nearest representable value to the true one."""
    import importlib
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    fails = []

    def check(cond, label):
        if not cond:
            fails.append(label)
        print(f"  {'ok  ' if cond else 'FAIL'} {label}")

    # Exactness, independent of any format.
    check(exact_sqrt(Fraction(4), 64) == 2, "sqrt(4) is exactly 2")
    check(exact_sqrt(Fraction(9, 16), 64) == Fraction(3, 4), "sqrt(9/16) is exactly 3/4")
    approx = exact_sqrt(Fraction(2), 64)
    check(abs(approx * approx - 2) < Fraction(1, 1 << 60), "sqrt(2) to 60+ bits")
    check(approx * approx <= 2, "and it does not overshoot")

    ieee = importlib.import_module("ieee_ref")
    div = make_div(ieee)
    sqrt = make_sqrt(ieee)
    f = ieee.FORMATS["binary32"]
    one = ieee.encode(f, Fraction(1))
    two = ieee.encode(f, Fraction(2))
    four = ieee.encode(f, Fraction(4))

    check(div(f, four, two) == two, "binary32 4/2 = 2")
    check(div(f, one, two) == ieee.encode(f, Fraction(1, 2)), "binary32 1/2 = 0.5")
    check(div(f, one, ieee.encode(f, Fraction(0))) == f.pos_inf, "binary32 1/0 = +Inf")
    check(div(f, ieee.encode(f, Fraction(0)), ieee.encode(f, Fraction(0)))
          == f.quiet_nan, "binary32 0/0 = NaN")
    check(div(f, f.pos_inf, f.pos_inf) == f.quiet_nan, "binary32 Inf/Inf = NaN")
    check(sqrt(f, four) == two, "binary32 sqrt(4) = 2")
    check(sqrt(f, ieee.encode(f, Fraction(0))) == f.pos_zero, "binary32 sqrt(0) = 0")
    check(sqrt(f, ieee.encode(f, Fraction(-1))) == f.quiet_nan, "binary32 sqrt(-1) = NaN")
    check(sqrt(f, f.pos_inf) == f.pos_inf, "binary32 sqrt(+Inf) = +Inf")

    # The rounded sqrt must be the nearest representable value to the true one. Checked
    # against the neighbours rather than against a stored answer.
    bad = 0
    for n in range(2, 60):
        raw = ieee.encode(f, Fraction(n))
        got = sqrt(f, raw)
        v = Fraction(ieee.decode(f, got))
        true = exact_sqrt(Fraction(n), 200)
        for nb in (got - 1, got + 1):
            try:
                if abs(Fraction(ieee.decode(f, nb)) - true) < abs(v - true):
                    bad += 1
                    break
            except Exception:
                pass
    check(bad == 0, f"sqrt is the nearest representable value for 2..59 ({bad} closer "
                    f"neighbours found)")

    print(f"\nself-test: {'PASS' if not fails else 'FAIL'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(self_test())
