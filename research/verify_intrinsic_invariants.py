#!/usr/bin/env python3
"""Sweep every golden oracle for intrinsic structural invariants.

Rationale: the strongest result of this campaign came from an invariant that
needs no external reference (see specs/numeric/negation_invariant.t27). This
script generalises that method across the whole oracle layer.

Three properties are tested, each checkable from the encoding alone:

  MONOTONIC   within the positive half, larger code -> larger value. True of
              IEEE-like layouts and of tapered formats (posit, takum), because
              both are designed so the integer ordering of codes matches the
              numeric ordering. A violation means the decode ladder is wrong
              somewhere.

  SIGN        the format's negation rule holds. Two conventions exist and the
              script reports which one (if either) the oracle obeys:
                sign-magnitude   decode(raw XOR msb)      == -decode(raw)
                two's complement decode((-raw) mod 2^n)   == -decode(raw)

  ROUNDTRIP   encode(decode(raw)) == raw for codes that decode to a finite value.
              Only run where the oracle exposes encode().

Formats that are structural (block scaling, shared exponent, stochastic rounding)
are not expected to satisfy these and are reported separately rather than scored.

Run:  python3 research/verify_intrinsic_invariants.py
Exit: 0 always — this is a survey, not a gate. Read the table.
"""
from __future__ import annotations
from fractions import Fraction
import importlib.util
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(REPO, "conformance")

MAX_ENUM = 1 << 16
SAMPLE = 4000

# Families where a monotone code ladder is not part of the design.
STRUCTURAL_HINTS = ("block", "shared", "stochastic", "per_channel", "q_format",
                    "tapered_fp", "unum", "minifloat", "bfp", "hybrid")


def load_oracles():
    out = {}
    for fn in sorted(os.listdir(CONF)):
        if not fn.endswith("_ref.py") or fn.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location("i_" + fn[:-3],
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
        for name, fmt in getattr(mod, "FORMATS", {}).items():
            out.setdefault(name, (mod, fmt, fn[:-7]))
    return out


def width_of(fmt, name):
    for attr in ("n", "width", "W", "total", "bits", "nbits"):
        v = getattr(fmt, attr, None)
        if isinstance(v, int) and v > 0:
            return v
    d = "".join(c for c in name if c.isdigit())
    return int(d) if d else 0


def finite(mod, fmt, raw):
    """Exact finite value as Fraction, or None."""
    try:
        v = mod.decode(fmt, raw)
    except Exception:
        return None
    if getattr(v, "kind", None) is not None:
        return None
    if isinstance(v, (int, Fraction)):
        return Fraction(v)
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError):
        return None
    if f != f or abs(f) == float("inf"):
        return None
    return Fraction(f)


def codes_for(width):
    span = 1 << width
    if span <= MAX_ENUM:
        return range(span), span
    return range(0, span, max(1, span // SAMPLE)), span


def check_monotonic(mod, fmt, width):
    """Strictly increasing over the positive half (codes below the MSB)."""
    span = 1 << width
    half = span >> 1
    if half <= 1:
        return None, 0
    step = 1 if half <= MAX_ENUM else max(1, half // SAMPLE)
    prev = None
    bad = 0
    tested = 0
    for raw in range(0, half, step):
        v = finite(mod, fmt, raw)
        if v is None:
            continue
        if prev is not None:
            tested += 1
            if v <= prev:
                bad += 1
        prev = v
    if tested == 0:
        return None, 0
    return bad == 0, tested


def check_sign(mod, fmt, width):
    """Return which negation convention holds: 'xor', 'twos', 'neither', None."""
    span = 1 << width
    msb = span >> 1
    if width < 2:
        return None
    codes, _ = codes_for(width)
    xor_ok = twos_ok = True
    tested = 0
    for raw in codes:
        if raw == 0 or raw == msb:
            continue
        a = finite(mod, fmt, raw)
        if a is None:
            continue
        bx = finite(mod, fmt, raw ^ msb)
        bt = finite(mod, fmt, (-raw) % span)
        if bx is None and bt is None:
            continue
        tested += 1
        if bx is None or bx != -a:
            xor_ok = False
        if bt is None or bt != -a:
            twos_ok = False
        if not xor_ok and not twos_ok and tested > 64:
            break
    if tested == 0:
        return None
    if xor_ok:
        return "xor"
    if twos_ok:
        return "twos"
    return "neither"


def check_roundtrip(mod, fmt, width):
    """decode(raw) -> encode(value) -> raw, with signed zero counted separately.

    Pass 159 opened the flags this raised. For binary16, bfloat16, fp8_e5m2, fp6_e2m3
    and gf16 the answer was the same every time: exactly ONE code out of the whole
    space fails, and it is the negative-zero code. The oracles carry values as
    `Fraction`, which cannot distinguish -0 from +0, so encode() returns the positive
    zero code and the round trip closes on the wrong one.

    That is a property of the carrier, not of the format -- the corpus already knows
    it, and crossval_ml_dtypes.py prints "[2 zero-sign not carried by oracle]" for the
    same reason. Reporting it as VIOLATED put 21 of 35 narrow formats on a flag list
    for a defect none of them has.

    It also explains why the flag tracked width. Exhaustive enumeration always reaches
    the negative-zero code; the stride sample used above 16 bits usually steps over it.

    So signed zero is counted apart, and anything else is a real round-trip failure.
    """
    if not hasattr(mod, "encode"):
        return None, 0
    codes, _ = codes_for(width)
    neg_zero_code = 1 << (width - 1)
    bad = tested = signed_zero = 0
    for raw in codes:
        v = finite(mod, fmt, raw)
        if v is None:
            continue
        try:
            back = mod.encode(fmt, v)
        except Exception:
            continue
        tested += 1
        if back == raw:
            continue
        if raw == neg_zero_code and v == 0:
            signed_zero += 1          # the carrier, not the format
            continue
        bad += 1
    if tested == 0:
        return None, 0
    return (bad == 0, tested) if not signed_zero else (bad == 0, tested)


def main() -> int:
    oracles = load_oracles()
    structural = []
    flagged = []

    # Streamed: exact-Fraction sweeps over 2^16 codes are slow, so results are
    # printed as they land rather than buffered to the end. A long run stays
    # observable instead of looking hung.
    print(f"{'format':<14}{'bits':>5}  {'monotonic':<11}{'negation':<11}{'roundtrip'}",
          flush=True)
    print("-" * 58, flush=True)

    for name in sorted(oracles):
        mod, fmt, family = oracles[name]
        width = width_of(fmt, name)
        if width == 0 or width > 64:
            continue
        if any(h in name for h in STRUCTURAL_HINTS):
            structural.append(name)
            continue
        mono, _ = check_monotonic(mod, fmt, width)
        sign = check_sign(mod, fmt, width)
        rt, _ = check_roundtrip(mod, fmt, width)

        m = "-" if mono is None else ("OK" if mono else "VIOLATED")
        s = "-" if sign is None else sign
        r = "-" if rt is None else ("OK" if rt else "VIOLATED")
        print(f"{name:<14}{width:>5}  {m:<11}{s:<11}{r}", flush=True)
        if mono is False or sign == "neither" or rt is False:
            flagged.append(name)

    print()
    if structural:
        print(f"structural / not scored ({len(structural)}): {', '.join(structural)}")
    print()
    if flagged:
        print(f"FLAGGED ({len(flagged)}): {', '.join(flagged)}")
        print("A flag is a lead, not a verdict — some are legitimate design choices.")
    else:
        print("No format violated any tested invariant.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
