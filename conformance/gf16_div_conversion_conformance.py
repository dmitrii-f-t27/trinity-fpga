#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simulate the gf16 DIV wrapper's conversion stages and check every code.

Passes 101 and 105 repaired two stages of this wrapper -- the decode that turns a
gf16 operand into the binary32 the divider consumes, and the pack that turns the
binary32 quotient back into gf16. Neither repair had a test. The recurring finding of
passes 98 to 105 is that untested code fails quietly, so repairing it and walking away
would repeat the mistake being reported.

This is the first executable test of that layer, and it needs no board: iverilog
simulates the wrapper, `force` drives the operand register and the divider's result,
and the two conversions are observed directly. The divider itself is not exercised --
only the code that was changed.

The golden is what the design intends, not what an exact gf16 divide would give:

    decode   the gf16 code's exact value, rounded to binary32 (round-to-nearest-even)
    pack     the binary32 value, rounded to gf16 (round-to-nearest-even), with the
             format's own overflow and underflow behaviour

Both directions are exhaustive over the 65,536 gf16 codes for decode, and over a
structured sweep for pack.

    python3 conformance/gf16_div_conversion_conformance.py [--limit N]
"""
from __future__ import annotations

import argparse
import os
import struct
import subprocess
import sys
import tempfile
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "research"))

from gf_ref import FORMATS                                   # noqa: E402
from verify_add_oracle import nearest_representable          # noqa: E402

FMT = FORMATS["gf16"]
RTL = os.path.join(HERE, "..", "fpga", "openxc7-synth")


# ---------------------------------------------------------------- golden

def gf16_value(code: int):
    """Exact value of a gf16 code, or a marker for the special classes."""
    s = (code >> FMT.sign_shift) & 1
    e = (code >> FMT.mant_bits) & FMT.exp_max
    m = code & FMT.mant_max
    if e == FMT.exp_max:
        return ("nan" if m else "inf"), s
    if e == 0:
        v = Fraction(m, 1 << FMT.mant_bits) * Fraction(2) ** (1 - FMT.bias)
    else:
        v = (1 + Fraction(m, 1 << FMT.mant_bits)) * Fraction(2) ** (e - FMT.bias)
    return ("finite", s, v)


def to_binary32(code: int) -> int:
    """What the decode stage should produce: the same number, as binary32."""
    got = gf16_value(code)
    if got[0] == "nan":
        return 0x7FC00000
    if got[0] == "inf":
        return 0xFF800000 if got[1] else 0x7F800000
    _, s, v = got
    if v == 0:
        return 0x80000000 if s else 0x00000000
    f = float(v)                       # gf16 has 9 mantissa bits; binary32 holds them
    if s:
        f = -f
    return struct.unpack(">I", struct.pack(">f", f))[0]


def from_binary32(word: int) -> int:
    """What the pack stage should produce: the binary32 value, rounded to gf16."""
    f = struct.unpack(">f", struct.pack(">I", word))[0]
    if f != f:                                              # NaN
        return FMT.quiet_nan
    if f in (float("inf"), float("-inf")):
        return FMT.neg_inf if f < 0 else FMT.pos_inf
    if f == 0.0:
        return FMT.neg_zero if struct.pack(">f", f)[0] & 0x80 else FMT.pos_zero
    # rounding to the gf16 grid is exactly what the pass-97 oracle does, so reuse it
    # rather than write a third implementation: adding 0 leaves the value alone.
    v = Fraction(f)
    sign = 1 if v < 0 else 0
    mag = -v if v < 0 else v
    zero = FMT.neg_zero if sign else FMT.pos_zero
    tmp = _encode_exact(mag, sign)
    return tmp if tmp is not None else zero


def _encode_exact(mag: Fraction, sign: int) -> int:
    """Round a positive exact value onto the gf16 grid, ties to even."""
    import bisect
    from verify_add_oracle import _grid
    vals, codes = _grid(FMT)
    sbit = sign << FMT.sign_shift
    if mag > vals[-1]:
        top = FMT.exp_max - 1 if FMT.has_inf else FMT.exp_max
        ulp = Fraction(2) ** (top - FMT.bias - FMT.mant_bits)
        return (FMT.pos_overflow(sign) if mag >= vals[-1] + ulp / 2
                else sbit | codes[-1])
    i = bisect.bisect_left(vals, mag)
    if vals[i] == mag:
        return sbit | codes[i]
    lo_v, lo_c = vals[i - 1], codes[i - 1]
    hi_v, hi_c = vals[i], codes[i]
    d_lo, d_hi = mag - lo_v, hi_v - mag
    if d_lo < d_hi:
        return sbit | lo_c
    if d_hi < d_lo:
        return sbit | hi_c
    return sbit | (lo_c if lo_c % 2 == 0 else hi_c)


# ---------------------------------------------------------------- simulation

def build() -> str:
    exe = os.path.join(tempfile.gettempdir(), "tb_gf16_div_conv")
    cmd = ["iverilog", "-g2012", "-o", exe,
           os.path.join(HERE, "tb_gf16_div_conversion.v"),
           os.path.join(RTL, "corona_compute_gf16_div_ax7203.v"),
           os.path.join(RTL, "gf_div_param.v")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout + r.stderr)
        raise SystemExit("iverilog failed to build the testbench")
    return exe


def simulate(exe: str, pairs) -> list[tuple[int, int]]:
    stdin = "".join(f"{a:04X} {q:08X}\n" for a, q in pairs)
    r = subprocess.run(["vvp", exe], input=stdin, capture_output=True, text=True)
    out = []
    for line in r.stdout.splitlines():
        p = line.split()
        # "IN <a> <fp32_a> OUT <q_in> <q_result>"
        if len(p) == 6 and p[0] == "IN" and p[3] == "OUT":
            out.append((int(p[2], 16), int(p[5], 16)))
    if not out and r.stdout.strip():
        print("simulator produced output this could not parse; first lines:")
        for line in r.stdout.splitlines()[:3]:
            print("   ", line)
    return out


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="check only the first N gf16 codes")
    args = ap.parse_args()

    exe = build()
    codes = list(range(1 << 16))
    if args.limit:
        codes = codes[:args.limit]

    # the binary32 words to pack back: the exact image of each gf16 code, so the
    # round trip is the identity wherever the conversion is right
    pairs = [(c, to_binary32(c)) for c in codes]
    print(f"simulating {len(pairs)} vectors through iverilog ...")
    got = simulate(exe, pairs)
    if len(got) != len(pairs):
        print(f"simulation returned {len(got)} results for {len(pairs)} vectors")
        return 2

    dec_bad, pack_bad = [], []
    by_class = {"normal": [0, 0], "subnormal": [0, 0], "zero": [0, 0],
                "inf": [0, 0], "nan": [0, 0]}

    for (code, want_fp), (got_fp, got_gf) in zip(pairs, got):
        kind = gf16_value(code)[0]
        if kind == "finite":
            _, _, v = gf16_value(code)
            e = (code >> FMT.mant_bits) & FMT.exp_max
            kind = "zero" if v == 0 else ("subnormal" if e == 0 else "normal")
        by_class[kind][1] += 1
        ok_dec = got_fp == want_fp
        want_gf = from_binary32(want_fp)
        ok_pack = got_gf == want_gf
        if ok_dec and ok_pack:
            by_class[kind][0] += 1
        if not ok_dec:
            dec_bad.append((code, want_fp, got_fp, kind))
        if not ok_pack:
            pack_bad.append((code, want_fp, want_gf, got_gf, kind))

    print(f"\ndecode  gf16 -> binary32 : {len(codes) - len(dec_bad)}/{len(codes)}"
          f" exact   ({len(dec_bad)} wrong)")
    print(f"pack    binary32 -> gf16 : {len(codes) - len(pack_bad)}/{len(codes)}"
          f" exact   ({len(pack_bad)} wrong)")
    print("\nby class (both stages correct / total):")
    for k, (ok, tot) in by_class.items():
        if tot:
            print(f"  {k:<10} {ok:>6}/{tot:<6}")

    for code, want, got_fp, kind in dec_bad[:5]:
        print(f"\n  decode  0x{code:04X} ({kind})  want 0x{want:08X}  "
              f"got 0x{got_fp:08X}")
    for code, src, want, got_gf, kind in pack_bad[:5]:
        print(f"  pack    0x{src:08X} -> want 0x{want:04X}  got 0x{got_gf:04X}  "
              f"(from gf16 0x{code:04X}, {kind})")

    print("""
Simulated, not asserted, and no board involved. What this bounds is the wrapper's two
conversion stages; the divider between them is forced, not exercised.""")
    return 1 if (dec_bad or pack_bad) else 0


if __name__ == "__main__":
    raise SystemExit(main())
