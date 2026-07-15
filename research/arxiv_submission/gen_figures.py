#!/usr/bin/env python3
"""Generate publication-quality figures for the Trinity arXiv paper.

Produces three PDFs (vector graphics) in this directory:
  1. format_comparison_accuracy.pdf  - grouped bar chart, mean rel err vs format
  2. format_comparison_lut.pdf       - LUT cost comparison (measured vs lit)
  3. catalog_coverage.pdf            - 83-format catalog oracle coverage pie

Run:  python3 research/arxiv_submission/gen_figures.py
"""

from __future__ import annotations

import csv
import os
import sys

import matplotlib

matplotlib.use("Agg")  # headless; safe for CI / no-display
import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
# Academic style: serif fonts, no grid, tight layout, reasonable DPI for preview.
# ---------------------------------------------------------------------------
plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": [
            "Times New Roman",
            "Times",
            "DejaVu Serif",
            "Liberation Serif",
        ],
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 12,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "axes.grid": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,  # embed TrueType outlines (arXiv-friendly)
        "ps.fonttype": 42,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05,
    }
)

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "..", "format_accuracy_results.csv")


# ===========================================================================
# Figure 1: Accuracy benchmark grouped bar chart
# ===========================================================================
def fig_accuracy() -> str:
    rows = []
    with open(CSV_PATH, newline="") as fh:
        for row in csv.DictReader(fh):
            rows.append(row)

    # Canonical format order / display labels.
    format_keys = [
        "GF16",
        "GF12",
        'Posit16,1',
        "MXFP8 (E4M3)",
        "BF16",
        "FP16",
        "Takum16",
    ]
    format_labels = [
        "GF16",
        "GF12",
        "Posit(16,1)",
        "MXFP8",
        "BF16",
        "FP16",
        "Takum16",
    ]
    suite_order = ["arithmetic", "dynamic_range", "cancellation", "edge_cases"]
    suite_labels = ["Arithmetic", "Dynamic range", "Cancellation", "Edge cases"]

    # 4-colour palette, colour-blind safe-ish, academic.
    colors = ["#1f77b4", "#2ca02c", "#d62728", "#9467bd"]

    # mean_rel_err[(suite, format)] = float
    mean_err = {}
    for r in rows:
        mean_err[(r["suite"], r["format"])] = float(r["mean_rel_err"])

    n_formats = len(format_keys)
    n_suites = len(suite_order)
    bar_w = 0.18
    x = np.arange(n_formats)

    fig, ax = plt.subplots(figsize=(9.0, 4.6))

    for i, (suite, label, color) in enumerate(
        zip(suite_order, suite_labels, colors)
    ):
        vals = [mean_err.get((suite, fmt), np.nan) for fmt in format_keys]
        offset = (i - (n_suites - 1) / 2.0) * bar_w
        ax.bar(
            x + offset,
            vals,
            bar_w,
            label=label,
            color=color,
            edgecolor="black",
            linewidth=0.5,
        )

    ax.set_yscale("log")
    ax.set_ylabel("Mean relative error (log scale)")
    ax.set_xticks(x)
    ax.set_xticklabels(format_labels, rotation=0)
    ax.set_title("Number Format Accuracy Comparison")
    ax.legend(
        loc="upper left",
        frameon=False,
        ncol=n_suites,
        columnspacing=1.2,
        handlelength=1.4,
    )
    ax.set_axisbelow(True)
    # subtle horizontal axis only.
    ax.spines["left"].set_visible(True)
    ax.spines["bottom"].set_visible(True)
    ax.tick_params(axis="x", which="both", length=0)
    y_min = min(
        v
        for (s, _), v in mean_err.items()
        if s in suite_order and v > 0 and np.isfinite(v)
    )
    ax.set_ylim(bottom=y_min * 0.3, top=2.0)

    out = os.path.join(HERE, "format_comparison_accuracy.pdf")
    fig.savefig(out)
    fig.savefig(out.replace(".pdf", ".png"), dpi=200)  # preview
    plt.close(fig)
    return out


# ===========================================================================
# Figure 2: LUT cost comparison
# ===========================================================================
def fig_lut() -> str:
    # (label, luts, category, note)
    # category in {"measured", "measured-dsp", "literature"}
    data = [
        ("GF16\n(old top)",            176, "measured",     ""),
        ("GF16\n(parametric)",         491, "measured",     ""),
        ("tekum16\n(stub)",            573, "measured",     ""),
        ("GF16 MAC-16",                 71, "measured-dsp", "+ 16 DSP"),
        ("Ternary MAC-16",              52, "measured",     "0 DSP"),
        ("Posit16\n(literature)",     1500, "literature",   ""),
        ("Takum16\n(literature)",      750, "literature",   ""),
    ]

    labels = [d[0] for d in data]
    luts = [d[1] for d in data]
    cats = [d[2] for d in data]
    notes = [d[3] for d in data]

    style = {
        "measured":      dict(color="#2ca02c", hatch="",  edgecolor="black"),
        "measured-dsp":  dict(color="#1f77b4", hatch="//", edgecolor="black"),
        "literature":    dict(color="#bbbbbb", hatch="\\\\", edgecolor="black"),
    }

    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    bars = []
    for i, (lab, lut, cat, note) in enumerate(data):
        b = ax.bar(
            [i],
            [lut],
            0.62,
            color=style[cat]["color"],
            hatch=style[cat]["hatch"],
            edgecolor=style[cat]["edgecolor"],
            linewidth=0.7,
            label=None,
        )
        bars.append(b[0])
        # value label above bar
        annot = f"{lut}"
        if note:
            annot += f"\n{note}"
        ax.text(
            i,
            lut + max(luts) * 0.012,
            annot,
            ha="center",
            va="bottom",
            fontsize=9,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("LUT count")
    ax.set_title("LUT Cost Comparison on openXC7 (Artix-7)")
    ax.set_ylim(0, max(luts) * 1.22)

    # Legend proxies for the three categories.
    from matplotlib.patches import Patch

    legend_handles = [
        Patch(facecolor=style["measured"]["color"],   edgecolor="black", label="Measured (openXC7)"),
        Patch(facecolor=style["measured-dsp"]["color"], edgecolor="black", hatch="//", label="Measured + DSP"),
        Patch(facecolor=style["literature"]["color"], edgecolor="black", hatch="\\\\", label="Literature (closed flow)"),
    ]
    ax.legend(handles=legend_handles, loc="upper left", frameon=False)

    out = os.path.join(HERE, "format_comparison_lut.pdf")
    fig.savefig(out)
    fig.savefig(out.replace(".pdf", ".png"), dpi=200)
    plt.close(fig)
    return out


# ===========================================================================
# Figure 3: Catalog coverage pie
# ===========================================================================
def fig_coverage() -> str:
    labels = ["With oracle (72)", "Structural (11)"]
    sizes = [72, 11]
    colors = ["#2ca02c", "#999999"]
    explode = (0.03, 0.03)

    fig, ax = plt.subplots(figsize=(5.2, 4.4))
    wedges, texts, autotexts = ax.pie(
        sizes,
        explode=explode,
        labels=labels,
        colors=colors,
        autopct=lambda p: f"{p:.1f}%\n({int(round(p * sum(sizes) / 100))})",
        startangle=90,
        wedgeprops=dict(edgecolor="black", linewidth=0.7),
        textprops=dict(fontsize=11),
        pctdistance=0.72,
    )
    for at in autotexts:
        at.set_color("white")
        at.set_fontsize(9)
        at.set_weight("bold")

    ax.set_title("83-Format Catalog Oracle Coverage")
    ax.axis("equal")

    out = os.path.join(HERE, "catalog_coverage.pdf")
    fig.savefig(out)
    fig.savefig(out.replace(".pdf", ".png"), dpi=200)
    plt.close(fig)
    return out


def main() -> int:
    print(f"CSV: {os.path.abspath(CSV_PATH)}")
    if not os.path.exists(CSV_PATH):
        print("ERROR: benchmark CSV not found.", file=sys.stderr)
        return 1
    outputs = [fig_accuracy(), fig_lut(), fig_coverage()]
    for o in outputs:
        sz = os.path.getsize(o)
        print(f"  wrote {os.path.relpath(o, HERE)}  ({sz} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
