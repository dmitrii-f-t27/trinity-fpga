#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
head_to_head.py — GF16 vs tekum16 vs takum16: accuracy + LUT cost comparison.

This is a focused three-way head-to-head:
  * GF16     — IEEE-754-style LINEAR float, exp/mant split = 6/9, bias=31.
               Source: conformance/gf_ref.py (canonical Trinity oracle).
  * tekum16  — LINEAR tapered precision (S|D|R(3)|characteristic|mantissa),
               working binary-takum lineage model of arXiv:2512.10964.
               Source: conformance/tekum_ref.py.
  * takum16  — LOGARITHMIC tapered precision (LNS) per arXiv:2404.18603
               (Hunhold, 2024). value = (-1)^S * exp(ell/2). Implemented here
               as a minimal self-contained oracle mirroring the t27 verified
               second witness used by conformance/takum16_decode_conformance_*.

Method:
  For each format, 500 random Fraction operands in [-100, 100] are drawn.
  For each pair (a, b):
    raw_a   = encode(a)
    raw_b   = encode(b)
    raw_sum = format_add(raw_a, raw_b)         # golden SW add for that format
    approx  = decode(raw_sum)                  # Fraction (or FP32-snapped)
    exact   = a + b                            # exact Fraction
    relerr  = |approx - exact| / |exact|
  Metrics: mean relerr, max relerr, pass count (relerr <= tol),
           non-finite count (NaR/Inf from finite inputs).

Output:
  * Formatted table to stdout.
  * CSV at research/head_to_head_results.csv.

Honesty: this is an ACCURACY + rough-LUT benchmark only. The LUT numbers are
literature-order estimates for openXC7/Artix-7 (no DSP, no carry-chain abuse);
they are NOT post-synthesis measurements. The takum16 path uses math.exp
snapped to FP32 — consistent with the t27 second-witness — which caps its
oracle precision at the FP32 grid (~1e-7). The accuracy ranking is therefore
illustrative, not a controlled experiment.

Author: Trinity catalog benchmark (Agent N + Agent S), 2026-07-14.
"""

import bisect
import csv
import math
import os
import random
import struct
import sys
from fractions import Fraction

# --- locate the canonical oracles -------------------------------------------
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, os.path.join(REPO_ROOT, "conformance"))
import gf_ref       # noqa: E402  (canonical GF oracle, Fraction-based, RNE)
import tekum_ref    # noqa: E402  (canonical tekum oracle, Fraction-based, RNE)


# ============================================================================
# Format oracle interface
# ============================================================================

class FormatOracle:
    name = "?"
    layout = "?"
    total_bits = 0

    def encode(self, x):
        """x: Fraction (finite, non-NaR). Returns raw int."""
        raise NotImplementedError

    def decode(self, raw):
        """raw: int. Returns Fraction (finite) or None for NaR/Inf/NaN."""
        raise NotImplementedError

    def add(self, a_raw, b_raw):
        """Returns raw int of the format's sum (golden SW add)."""
        raise NotImplementedError


# ----------------------------------------------------------------------------
# GF16 — IEEE-754-style linear float (wraps canonical gf_ref oracle)
# ----------------------------------------------------------------------------

class GF16(FormatOracle):
    name = "GF16"
    layout = "[1|6|9] linear IEEE-style, bias=31, +Inf/NaN"
    total_bits = 16
    fmt = gf_ref.FORMATS["gf16"]

    def encode(self, x):
        if x == 0:
            return self.fmt.pos_zero
        return gf_ref.encode(self.fmt, x)

    def decode(self, raw):
        v = gf_ref.decode(self.fmt, raw)
        return None if isinstance(v, gf_ref.Special) else v

    def add(self, a_raw, b_raw):
        return gf_ref.gf_add(self.fmt, a_raw, b_raw)


# ----------------------------------------------------------------------------
# tekum16 — linear tapered precision (wraps canonical tekum_ref oracle)
# ----------------------------------------------------------------------------

class Tekum16(FormatOracle):
    name = "tekum16"
    layout = "[S|D|R(3)|char|mant] LINEAR tapered"
    total_bits = 16
    fmt = tekum_ref.FORMATS["tekum16"]

    def encode(self, x):
        if x == 0:
            return self.fmt.pos_zero
        return tekum_ref.encode(self.fmt, x)

    def decode(self, raw):
        v = tekum_ref.decode(self.fmt, raw)
        return None if isinstance(v, tekum_ref.Special) else v

    def add(self, a_raw, b_raw):
        return tekum_ref.tekum_add(self.fmt, a_raw, b_raw)


# ----------------------------------------------------------------------------
# takum16 — LOGARITHMIC tapered precision (LNS) per arXiv:2404.18603
# ----------------------------------------------------------------------------
# Format (mirrors the t27 verified second witness; see
# conformance/takum16_decode_conformance_ax7203.py):
#   bit[15]      = S   (sign)
#   bit[14]      = D   (direction: D=1 near unity, D=0 toward extremes)
#   bit[13:11]   = R   (regime, 3 bits)
#   payload(11)  = [ C_u (r_eff bits) | M_u (p bits) ]
#       r_eff = D ? R : (7 - R)
#       p     = 16 - 5 - r_eff                  (the TAPER)
#       c     = CBIAS[{D,R}] + C_u              (signed characteristic)
#       m     = M_u / 2^p                       (linear mantissa fraction)
#       ell   = (1 - 2*S) * (c + m)
#   value = (-1)^S * exp(ell / 2)
#   specials: raw == 0 -> +0 ; raw == 0x8000 -> NaR
#
# Addition: takum is logarithmic, so addition CANNOT be done directly in the
# encoded domain. The golden SW path is: decode -> linear add (Fraction) ->
# encode. Hardware implementations either (a) use the same decode-add-encode
# flow with BRAM LUTs for exp()/log2(), or (b) use Zech-log approximations.

_T16_N      = 16
_T16_CBIAS  = (-255, -127, -63, -31, -15, -7, -3, -1,
                 0,    1,   3,   7,  15, 31, 63, 127)
_T32_MAX    = struct.unpack('>f', b'\x7f\x7f\xff\xff')[0]   # ~3.4028e38
# IMPORTANT: takum's S bit does NOT simply flip the sign. Per the t27 verified
# second-witness (conformance/takum16_decode_*), value = (-1)^S * exp(ell/2)
# with ell = (1 - 2*S) * (c + m). For S=1 this gives |value| = exp(-(c+m)/2),
# i.e. the negative of a value uses the RECIPROCAL magnitude encoding. Encodes
# must therefore bisect over SIGNED decoded values, not flip a sign bit.


def _takum16_decode_raw(raw):
    """raw -> Fraction (FP32-snapped) | None for NaR/overflow."""
    raw &= 0xFFFF
    if raw == 0:
        return Fraction(0)
    if raw == (1 << (_T16_N - 1)):
        return None                                # NaR
    S = (raw >> 15) & 1
    D = (raw >> 14) & 1
    R = (raw >> 11) & 7
    cbias = _T16_CBIAS[(D << 3) | R]
    r_eff = R if D else (7 - R)
    p = _T16_N - 5 - r_eff
    if p < 0:
        p = 0
    lower = raw & ((1 << (r_eff + p)) - 1)
    M_u = (lower & ((1 << p) - 1)) if p > 0 else 0
    C_u = ((lower >> p) & ((1 << r_eff) - 1)) if r_eff > 0 else 0
    c = cbias + C_u
    m = Fraction(M_u, 1 << p) if p > 0 else Fraction(0)
    ell = (1 - 2 * S) * (Fraction(c) + m)
    # value = exp(ell/2). Use float math; snap to binary32 RNE so the oracle
    # matches the t27 second-witness (the format's natural decode target).
    try:
        val = math.exp(float(ell) / 2.0)
    except OverflowError:
        return None
    except ValueError:
        return None
    if not math.isfinite(val):
        return None
    if val > _T32_MAX:
        return None                                # clamps to +Inf in binary32
    f32 = struct.unpack('>f', struct.pack('>f', val))[0]
    if f32 == 0.0:
        return Fraction(0)
    return Fraction(f32) * (-1 if S else 1)


class Takum16(FormatOracle):
    name = "takum16"
    layout = "[S|D|R(3)|char|mant] LOGARITHMIC LNS"
    total_bits = 16

    # Full 65536-entry decode table (lazy). Encode via bisect on sorted values.
    _TABLE   = None
    _VALUES  = None
    _RAWS    = None

    @classmethod
    def _build(cls):
        if cls._TABLE is not None:
            return
        table = [(raw, _takum16_decode_raw(raw)) for raw in range(1 << _T16_N)]
        # Signed sort (negatives first): bisection target is the decoded value
        # itself, not its magnitude, because takum's S bit changes the encoded
        # magnitude (negative values use the reciprocal's log).
        finite = sorted((v, r) for (r, v) in table if v is not None and v != 0)
        cls._TABLE  = table
        cls._VALUES = [v for (v, _r) in finite]
        cls._RAWS   = [r for (v, r) in finite]

    def encode(self, x):
        self._build()
        if x == 0:
            return 0
        i = bisect.bisect_left(self._VALUES, x)
        best = None
        best_d = None
        for j in (i - 1, i, i + 1):
            if 0 <= j < len(self._VALUES):
                d = abs(self._VALUES[j] - x)
                if best_d is None or d < best_d:
                    best_d = d
                    best = self._RAWS[j]
        return best

    def decode(self, raw):
        self._build()
        return self._TABLE[raw & 0xFFFF][1]

    def add(self, a_raw, b_raw):
        a = self.decode(a_raw)
        b = self.decode(b_raw)
        if a is None or b is None:
            return 1 << (_T16_N - 1)                # NaR
        s = a + b
        if s == 0:
            return 0
        return self.encode(s)


# ============================================================================
# LUT cost estimates (literature-order, openXC7 / Artix-7, no DSP, no carry)
# ============================================================================
# These are NOT post-synthesis numbers. They reflect datapath complexity:
#  * IEEE-style linear (GF16): fixed exp/mant split -> simple comparator +
#    barrel-shift align + integer add + RNE round.
#  * Tapered linear (tekum16): variable exp/mant split -> regime decode +
#    barrel align by variable amount + add + regime re-selection on overflow.
#  * Tapered logarithmic (takum16): LNS -> exp()/log() needed for linearized
#    add. Two HW strategies: (1) pure logic (exp/log approximation via shift-
#    add, ~1500 LUT), or (2) 65536-entry BRAM LUT for decode + log-recode
#    LUT for encode (~50 LUT + 2 BRAM18, the approach used by the existing
#    fpga/openxc7-synth/takum16_decode.v).

LUT_ESTIMATES = {
    # name  : (lut_low, lut_high, notes)
    "GF16":    (110, 130,
                "exp cmp + 9-bit mantissa align + 9-bit add + RNE round "
                "(fixed 6/9 field split, no regime decode)"),
    "tekum16": (480, 650,
                "3-bit regime decode + variable-field barrel-shift align + "
                "add + tapered regime re-selection on overflow/repack"),
    "takum16": (1350, 1700,
                "pure-logic LNS: shift-add exp()/log() approx + Zech-log add; "
                "ALT: ~50 LUT + 2 BRAM18 if using 64K-entry LUT (current HW path)"),
}


# ============================================================================
# Dynamic range
# ============================================================================

def dynamic_range(fmt):
    """Return (min_normal, max_finite) as floats for the format."""
    if isinstance(fmt, GF16):
        # smallest normal exp_field=1, mant=0; max finite exp_field=62, mant=max
        f = GF16.fmt
        min_norm = float(math.pow(2.0, 1 - f.bias))
        max_e = (f.exp_max - 1) if f.has_inf else f.exp_max
        max_fin = float((1 + f.mant_max / (1 << f.mant_bits)) *
                        math.pow(2.0, max_e - f.bias))
        return (min_norm, max_fin)
    if isinstance(fmt, Tekum16):
        # Linear tapered: extreme exponents are at r_eff = 7 (low precision)
        # where c ranges over the CBIAS-spanned interval. Min = 2^(-255),
        # max = 2^(127 + 127) = 2^254 (linear interpretation).
        return (math.pow(2.0, -255), math.pow(2.0, 254))
    if isinstance(fmt, Takum16):
        # ell ranges over [cbias_min, cbias_max + 1] ~ [-255, 128]. value =
        # exp(ell/2). Cap by binary32 max since decode snaps to FP32.
        return (math.exp(-255.0 / 2.0), min(math.exp(128.0 / 2.0), _T32_MAX))
    return (0.0, 0.0)


# ============================================================================
# Benchmark core
# ============================================================================

def relerr(approx, exact):
    """|approx - exact| / |exact|, as float. 0==0 -> 0.0; 0 vs nonzero -> inf."""
    ef = float(exact)
    af = float(approx)
    if ef == 0.0:
        return 0.0 if af == 0.0 else float("inf")
    return abs(af - ef) / abs(ef)


def benchmark(fmt, n=500, seed=42, lo=-100.0, hi=100.0,
              tols=(1e-2, 1e-3, 1e-4)):
    """Run n random add ops and score relative error.

    `tols` is a tuple of thresholds at which pass-counts are reported. The
    default (1e-2, 1e-3, 1e-4) brackets the natural precision of ~9-11 bit
    formats: 1e-2 separates catastrophic from acceptable error, 1e-3 is the
    ~half-ULP floor for 9-10 mantissa bits, 1e-4 captures tapered formats
    near unity where they have up to 11 bits.
    """
    rng = random.Random(seed)
    sum_re = 0.0
    max_re = 0.0
    nonfinite = 0
    n_valid = 0
    pass_counts = {t: 0 for t in tols}

    for _ in range(n):
        a = Fraction(rng.uniform(lo, hi))
        b = Fraction(rng.uniform(lo, hi))
        exact = a + b

        ra = fmt.encode(a)
        rb = fmt.encode(b)
        rsum = fmt.add(ra, rb)
        approx = fmt.decode(rsum)

        if approx is None:
            nonfinite += 1
            continue
        n_valid += 1
        re = relerr(approx, exact)
        sum_re += re
        if re > max_re:
            max_re = re
        for t in tols:
            if re <= t:
                pass_counts[t] += 1

    mean_re = sum_re / n_valid if n_valid > 0 else float("nan")
    return {
        "name":         fmt.name,
        "layout":       fmt.layout,
        "n_tested":     n,
        "n_valid":      n_valid,
        "n_nonfinite":  nonfinite,
        "pass_1e2":     pass_counts[1e-2],
        "pass_1e3":     pass_counts[1e-3],
        "pass_1e4":     pass_counts[1e-4],
        "pass_1e2_pct": 100.0 * pass_counts[1e-2] / max(1, n_valid),
        "pass_1e3_pct": 100.0 * pass_counts[1e-3] / max(1, n_valid),
        "pass_1e4_pct": 100.0 * pass_counts[1e-4] / max(1, n_valid),
        "mean_relerr":  mean_re,
        "max_relerr":   max_re,
    }


# ============================================================================
# Reporting
# ============================================================================

def format_relerr(x):
    if x == float("inf"):
        return "  inf"
    if math.isnan(x):
        return "  nan"
    return f"{x:.4e}"


def print_table(rows):
    hdr = f"{'Format':<10} {'mean_relerr':>13} {'max_relerr':>13} " \
          f"{'pass@1e-2':>10} {'pass@1e-3':>10} {'pass@1e-4':>10} {'NaR/Inf':>9}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['name']:<10} {format_relerr(r['mean_relerr']):>13} "
              f"{format_relerr(r['max_relerr']):>13} "
              f"{r['pass_1e2']:>4}/{r['n_valid']:<4} "
              f"{r['pass_1e3']:>4}/{r['n_valid']:<4} "
              f"{r['pass_1e4']:>4}/{r['n_valid']:<4} "
              f"{r['n_nonfinite']:>9}")


def print_lut_table():
    print("\nLUT cost estimates (openXC7 / Artix-7, no DSP, no carry):")
    hdr = f"{'Format':<10} {'LUT low':>9} {'LUT high':>10}  notes"
    print(hdr)
    print("-" * 78)
    for name, (lo, hi, notes) in LUT_ESTIMATES.items():
        print(f"{name:<10} {lo:>9} {hi:>10}  {notes}")
    print("\n(sources: Trinity openXC7 GF16 cells; posit/takum VHDL codec numbers")
    print(" from Hunhold arXiv:2408.10594; tekum estimate by analogy to takum")
    print(" tapered datapath; PURE-LOGIC estimate for takum16 add, BRAM-LUT")
    print(" alternative in parens.)")


def print_range_table(formats):
    print("\nDynamic range (per-format decode):")
    hdr = f"{'Format':<10} {'min|value|':>15} {'max|value|':>15}"
    print(hdr)
    print("-" * len(hdr))
    for fmt in formats:
        lo, hi = dynamic_range(fmt)
        print(f"{fmt.name:<10} {lo:>15.4e} {hi:>15.4e}")


def write_csv(rows, path):
    cols = ["name", "layout", "n_tested", "n_valid", "n_nonfinite",
            "pass_1e2", "pass_1e3", "pass_1e4",
            "pass_1e2_pct", "pass_1e3_pct", "pass_1e4_pct",
            "mean_relerr", "max_relerr"]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r.get(c, "") for c in cols])


# ============================================================================
# main
# ============================================================================

def main():
    formats = [GF16(), Tekum16(), Takum16()]
    print("=" * 82)
    print("  GF16  vs  tekum16  vs  takum16  —  head-to-head")
    print("  500 random Fraction operands in [-100, 100]")
    print("  pass@tol: count of relerr <= tol  (formats have ~9-11 bit precision)")
    print("=" * 82)

    rows = [benchmark(f, n=500, seed=42, lo=-100.0, hi=100.0) for f in formats]

    print_table(rows)
    print_lut_table()
    print_range_table(formats)

    out_csv = os.path.join(os.path.dirname(__file__), "head_to_head_results.csv")
    write_csv(rows, out_csv)
    print(f"\nCSV written: {out_csv}")

    # ---- one-line summary ----
    gf   = next(r for r in rows if r["name"] == "GF16")
    teku = next(r for r in rows if r["name"] == "tekum16")
    tku  = next(r for r in rows if r["name"] == "takum16")
    winner_mean = min(rows, key=lambda r: r["mean_relerr"])["name"]
    winner_max  = min(rows, key=lambda r: r["max_relerr"])["name"]
    print("\nSummary:")
    print(f"  lowest mean relerr : {winner_mean}")
    print(f"  lowest max  relerr : {winner_max}")
    print(f"  GF16    : mean={format_relerr(gf['mean_relerr'])}  "
          f"max={format_relerr(gf['max_relerr'])}  "
          f"pass@1e-3={gf['pass_1e3']}/{gf['n_valid']}")
    print(f"  tekum16 : mean={format_relerr(teku['mean_relerr'])}  "
          f"max={format_relerr(teku['max_relerr'])}  "
          f"pass@1e-3={teku['pass_1e3']}/{teku['n_valid']}")
    print(f"  takum16 : mean={format_relerr(tku['mean_relerr'])}  "
          f"max={format_relerr(tku['max_relerr'])}  "
          f"pass@1e-3={tku['pass_1e3']}/{tku['n_valid']}  "
          f"(oracle precision capped at FP32 grid)")


if __name__ == "__main__":
    main()
