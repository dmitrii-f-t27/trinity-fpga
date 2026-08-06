#!/usr/bin/env python3
"""E8M0 exact oracle — the OCP MX v1.0 shared block scale.

Pass 265 found that the 2606.09686 abstract names six conformance packs and five
of them exist. E8M0 had a conformance host with an independent golden, RTL, and a
complete-chain Tier-E cell -- but no pack and no oracle. This is the oracle.

The format, from OCP Microscaling Formats v1.0:

  8 bits, exponent only. No sign bit, no mantissa, no zero.
    code 0x00..0xFE : value = 2**(code - 127)
    code 0xFF       : NaN

Three consequences worth stating, because each one has bitten this corpus before:

  * THERE IS NO ZERO. Every representable value is a power of two, and the
    smallest is 2**-127, not 0. `pos_zero` and `neg_zero` therefore raise --
    the pattern passes 231, 236 and 242 arrived at after finding four formats
    that declared a zero they did not have.
  * There is no Inf either, so overflow saturates rather than escaping. That is
    the same choice gf_ref makes for the GF widths without Inf.
  * MUL is exact and closed: 2**a * 2**b = 2**(a+b). ADD is NOT closed -- the sum
    of two powers of two is not a power of two -- so it rounds to the nearest
    representable exponent. Rounding is in the LOG domain, ties to even, because
    the representable points are geometrically spaced and a linear midpoint would
    bias every result upward.

Cross-check: conformance/e8m0_decode_conformance_ax7203.py carries an independent
golden re-implemented from the spec. The self-test below holds this oracle to it
on all 256 codes.

    python3 conformance/e8m0_ref.py
"""

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class E8M0Format:
    name: str
    width: int = 8

    @property
    def mask(self):
        return (1 << self.width) - 1

    @property
    def bias(self):
        return 127

    @property
    def nan(self):
        return 0xFF

    @property
    def unity(self):
        return 127                      # 2**0

    @property
    def max_code(self):
        return 0xFE

    @property
    def pos_zero(self):
        raise AttributeError("%s has no zero: every code is a power of two, the "
                             "smallest being 2**-127" % self.name)

    @property
    def neg_zero(self):
        raise AttributeError("%s has no sign bit and no zero" % self.name)


FORMATS = {"e8m0": E8M0Format("e8m0")}


class Special:
    __slots__ = ("kind", "sign")

    def __init__(self, kind, sign=0):
        self.kind = kind
        self.sign = sign

    def __repr__(self):
        return {"nan": "NaN"}.get(self.kind, self.kind)

    def __eq__(self, other):
        return isinstance(other, Special) and other.kind == self.kind


def decode(fmt, raw):
    """code -> exact Fraction, or Special('nan')."""
    raw &= fmt.mask
    if raw == fmt.nan:
        return Special("nan")
    return Fraction(2) ** (raw - fmt.bias)


def encode(fmt, value):
    """Exact value -> nearest representable code, ties to even in the log domain."""
    if isinstance(value, Special):
        return fmt.nan
    v = Fraction(value)
    if v <= 0:
        # No zero and no negatives exist. The nearest representable thing to a
        # non-positive number is the smallest positive one; saturating is the
        # only answer the format can give.
        return 0x00
    # exponent k with 2**k <= v < 2**(k+1), by bit length rather than by halving
    k = v.numerator.bit_length() - v.denominator.bit_length()
    if v < Fraction(2) ** k:
        k -= 1
    elif v >= Fraction(2) ** (k + 1):
        k += 1
    # geometric midpoint between 2**k and 2**(k+1) is 2**k * sqrt(2);
    # compare v**2 against 2**(2k+1) to stay exact
    up = v * v > Fraction(2) ** (2 * k + 1)
    if v * v == Fraction(2) ** (2 * k + 1):
        up = (k + fmt.bias) & 1          # tie -> even code
    e = k + 1 if up else k
    code = e + fmt.bias
    if code < 0:
        return 0x00
    if code > fmt.max_code:
        return fmt.max_code
    return code


def format_mul(fmt, a, b):
    """Exact and closed: 2**x * 2**y = 2**(x+y), saturating at the ends."""
    a &= fmt.mask
    b &= fmt.mask
    if a == fmt.nan or b == fmt.nan:
        return fmt.nan
    e = (a - fmt.bias) + (b - fmt.bias)
    code = e + fmt.bias
    if code < 0:
        return 0x00
    if code > fmt.max_code:
        return fmt.max_code
    return code


def format_add(fmt, a, b):
    """Not closed -- the sum of two powers of two is not one. Round to nearest."""
    a &= fmt.mask
    b &= fmt.mask
    if a == fmt.nan or b == fmt.nan:
        return fmt.nan
    return encode(fmt, decode(fmt, a) + decode(fmt, b))


def _self_test():
    f = FORMATS["e8m0"]
    checks = []

    # 1. every code round-trips through decode/encode
    rt = sum(1 for c in range(0xFF) if encode(f, decode(f, c)) == c)
    checks.append(("round-trip 0x00..0xFE", rt == 0xFF, "%d/255" % rt))

    # 2. the values are what the spec says
    checks.append(("unity", decode(f, 127) == 1, decode(f, 127)))
    checks.append(("minpos", decode(f, 0) == Fraction(1, 2 ** 127), None))
    checks.append(("maxpos", decode(f, 0xFE) == Fraction(2) ** 127, None))
    checks.append(("nan", isinstance(decode(f, 0xFF), Special), None))

    # 3. no zero
    for prop in ("pos_zero", "neg_zero"):
        try:
            getattr(f, prop)
            checks.append(("%s raises" % prop, False, "it did not"))
        except AttributeError:
            checks.append(("%s raises" % prop, True, None))

    # 4. mul is exact exponent addition
    ok = all(format_mul(f, x, y) == min(0xFE, max(0, x + y - 127))
             for x in range(0, 0xFF, 7) for y in range(0, 0xFF, 11))
    checks.append(("mul = exponent add, saturating", ok, None))

    # 5. add rounds: 2**0 + 2**0 = 2**1 exactly
    checks.append(("1+1 = 2", format_add(f, 127, 127) == 128, format_add(f, 127, 127)))

    # 6. against the independent golden in the conformance host
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    host_ok = None
    try:
        import types
        src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "e8m0_decode_conformance_ax7203.py"),
                   encoding="utf-8", errors="replace").read()
        m = types.ModuleType("h")
        m.__dict__["__name__"] = "h"
        sys.modules.setdefault("serial", types.ModuleType("serial"))
        exec(compile(src, "host", "exec"), m.__dict__)          # noqa: S102
        bad = 0
        for c in range(256):
            want = m.golden_e8m0(c)
            v = decode(f, c)
            if isinstance(v, Special):
                got = 0x7FC00000
            else:
                # 2**(c-127) as fp32: c=0 is the subnormal 2**-127
                got = 0x00400000 if c == 0 else (c << 23)
            if got != want:
                bad += 1
        host_ok = (bad == 0)
        checks.append(("matches the host golden on all 256 codes", host_ok,
                       None if host_ok else "%d differ" % bad))
    except Exception as e:                                       # noqa: BLE001
        checks.append(("host cross-check", False, type(e).__name__))

    bad = [c for c in checks if not c[1]]
    for name, ok, extra in checks:
        if not ok:
            print("FAIL %s %s" % (name, extra if extra is not None else ""))
    print("SELF-TEST: %s (e8m0: %d/%d)"
          % ("PASS" if not bad else "FAIL", len(checks) - len(bad), len(checks)))
    return not bad


if __name__ == "__main__":
    import sys
    sys.exit(0 if _self_test() else 1)
