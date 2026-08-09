#!/usr/bin/env python3
"""Figures for the TNF paper, in the house style of research/arxiv_submission.

Vector PDFs, headless backend, one figure per claim. Numbers are the measured
ones; nothing here is drawn from an estimate.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({
    "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
    "legend.fontsize": 8, "figure.dpi": 150, "savefig.bbox": "tight",
})

# ── 1. accuracy against tekum16, by binary-exponent magnitude ────────────────
# ── 1. accuracy, COMPUTED from the oracles rather than transcribed ──────────
#
# These numbers were hardcoded until 2026-08-09 and drifted: they still carried
# TNF16 at M = 9 and the label "tekum16" long after the rung moved to M = 11 and
# the oracle was shown to decode identically to takum. A figure that disagrees
# with the table it illustrates is the same defect class as a gate that cannot go
# red, so the figure now derives its own data.
import sys
from fractions import Fraction as F
sys.path.insert(0, "../../conformance")
import tnf_ref as T
import takum_ref as K
import gf_ref as G

BINS = [("|e| < 8", 0, 8), ("|e| 8–20", 8, 20), ("|e| 20–38", 20, 38)]
_rng = np.random.default_rng(20260809)
_vals = [float(s) * float(m) * 2.0 ** int(e) for s, m, e in
         zip(_rng.choice([-1, 1], 6000), _rng.uniform(1, 2, 6000),
             _rng.integers(-38, 39, 6000))]

def _mean_err(decode):
    out = []
    for _, lo, hi in BINS:
        tot, n = F(0), 0
        for v in _vals:
            if not lo <= abs(np.log2(abs(v))) < hi:
                continue
            d = decode(v)
            if d is None or d == 0:
                continue
            tot += abs(F(d) - F(v)) / abs(F(v)); n += 1
        out.append(float(tot / n) if n else float("nan"))
    return out

_tef = T.TNFFormat(4, 11)          # M = 11 as adopted; see t27#2005
_gf16 = G.FORMATS["gf16"]
_tk = K.TakumFormat("takum16", 16)

def _d_tef(v):
    try:
        return float(T.decode(_tef, T.encode(_tef, v)))
    except Exception:
        return None

def _d_gf(v):
    try:
        return float(G.decode(_gf16, G.encode(_gf16, v)))
    except Exception:
        return None

def _d_tk(v):
    try:
        r = K.decode(_tk, K.encode(_tk, v))
        return float(r) if not isinstance(r, K.Special) else None
    except Exception:
        return None

bins = [b[0] for b in BINS]
tef = _mean_err(_d_tef)
tak = _mean_err(_d_tk)
gf16 = _mean_err(_d_gf)

x = np.arange(len(bins)); w = 0.27
fig, ax = plt.subplots(figsize=(5.2, 2.9))
ax.bar(x - w, gf16, w, label="GF16 (φ)", color="#b9c6c1")
ax.bar(x,     tef,  w, label="TNF16 (M=11)", color="#0a7a4c")
ax.bar(x + w, tak,  w, label="takum16", color="#7d8f99")
ax.set_yscale("log")
ax.set_ylabel("mean relative round-trip error")
ax.set_xticks(x); ax.set_xticklabels(bins)
ax.set_title("Accuracy by binary-exponent magnitude (bins are powers of two)")
ax.legend(frameon=False)
for i, (g, t) in enumerate(zip(tef, tak)):
    ax.annotate(f"{t / g:.2f}×", (i, max(g, t) * 1.35),
                ha="center", fontsize=8, color="#0a7a4c")
fig.savefig("tnf_accuracy.pdf")
print("tnf_accuracy.pdf  ratios:", " ".join(f"{t/g:.2f}x" for g, t in zip(tef, tak)))

# ── 2. the ladder: area and frequency ───────────────────────────────────────
rungs = ["TNF4", "TNF8", "TNF16", "TNF32", "TNF64"]
luts = [12, 50, 212, 1477, 7479]
fmax = [161.11, 153.23, 131.73, 83.27, 48.20]

fig, ax1 = plt.subplots(figsize=(5.2, 2.9))
ax1.bar(rungs, luts, 0.5, color="#0a7a4c")
ax1.set_ylabel("LUTs (no DSP48)", color="#0a7a4c")
ax1.tick_params(axis="y", labelcolor="#0a7a4c")
ax1.set_yscale("log")
for i, v in enumerate(luts):
    ax1.annotate(f"{v:,}", (i, v * 1.15), ha="center", fontsize=8, color="#0a7a4c")
ax2 = ax1.twinx()
ax2.plot(rungs, fmax, "o--", color="#333", linewidth=1.3, markersize=5)
ax2.set_ylabel("$F_{max}$ (MHz), post-route", color="#333")
ax2.set_ylim(0, 190)
for i, v in enumerate(fmax):
    ax2.annotate(f"{v:.1f}", (i, v + 8), ha="center", fontsize=8)
ax1.set_title("TNF multiplier on XC7A200T, one cycle of latency")
fig.savefig("tnf_ladder.pdf")
print("tnf_ladder.pdf")

# ── 3. what the interface width cost ────────────────────────────────────────
labels = ["32-bit ports\n(as written)", "widths derived\nfrom parameters", "+ one pipeline\nregister"]
lut3 = [1179, 219, 219]
f3 = [81.0, 81.35, 147.32]
fig, ax = plt.subplots(figsize=(5.2, 2.9))
b = ax.bar(labels, lut3, 0.5, color=["#c46a6a", "#0a7a4c", "#0a7a4c"])
ax.set_ylabel("LUTs")
ax.set_title("TNF16 multiplier: interface width dominates the arithmetic")
for i, (l, f) in enumerate(zip(lut3, f3)):
    ax.annotate(f"{l:,} LUT\n{f:.2f} MHz", (i, l + 40), ha="center", fontsize=8)
ax.annotate("3 × DSP48", (0, 1179 * 0.45), ha="center", fontsize=8, color="white")
ax.annotate("0 DSP48", (1, 219 * 0.45), ha="center", fontsize=8, color="white")
ax.annotate("0 DSP48", (2, 219 * 0.45), ha="center", fontsize=8, color="white")
ax.set_ylim(0, 1450)
fig.savefig("tnf_width.pdf")
print("tnf_width.pdf")
