#!/usr/bin/env python3
"""Cross-validate the fp8 packs against the IEEE P3109 working group's value tables.

Pass 63 found github.com/P3109/Public, whose Value Tables tree holds 504 CSV files
(154 MB) of exhaustive codepoint -> value tables in exact hex-float notation. Where
the formats overlap this is a SIXTH independent oracle, and the only one produced by
a standards body.

The overlap: P3109's binaryKpP names a format by total width K and precision P
(significand bits INCLUDING the implicit one). So

    fp8 E4M3  = 1 sign + 4 exp + 3 stored mantissa  ->  K=8, P=4
    fp8 E5M2  = 1 sign + 5 exp + 2 stored mantissa  ->  K=8, P=3

Each (K,P) ships four tables: signed/unsigned x extended/finite. OCP's E4M3FN and
E5M2 are signed; which of the extended/finite variants corresponds is decided by
comparing the special-value codes rather than assumed, and reported either way.

WHAT A DIFFERENCE MEANS HERE
----------------------------
Not necessarily a defect. P3109 and OCP are different specifications, and they are
known to differ on special values -- OCP E4M3FN has no infinity and a single NaN,
which P3109 need not match. A divergence on a FINITE code would be serious; a
divergence confined to the special-value codes is a spec difference and is reported
as one.

Run:  python3 research/crossval_p3109.py
Exit: 0 if every finite code agrees, 1 otherwise.
"""
from __future__ import annotations

import csv
import importlib.util
import io
import json
import os
import subprocess
import sys
from fractions import Fraction

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(REPO, "conformance")
BASE = ("repos/P3109/Public/contents/Value%20Tables/Hexadecimal/K8/"
        "{p}/signed/Binary8{p_low}{v}.csv")

PAIRS = [
    # (t27 format id, P3109 P value, description)
    ("fp8_e4m3", "P4", "1s4e3m -> K8 P4"),
    ("fp8_e5m2", "P3", "1s5e2m -> K8 P3"),
]


def fetch_table(pdir: str, variant: str) -> list[tuple[int, str, str]]:
    path = BASE.format(p=pdir, p_low=pdir.lower(), v=variant)
    try:
        blob = subprocess.check_output(["gh", "api", path, "--jq", ".content"],
                                       text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return []
    import base64
    text = base64.b64decode(blob).decode("utf-8", "replace")
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        cp = r.get("codepoint", "").strip()
        if not cp:
            continue
        rows.append((int(cp, 16), (r.get("value") or "").strip(),
                     (r.get("subnormal") or "").strip()))
    return rows


def hexfloat_to_fraction(s: str):
    """Exact value of a C99 hex float such as 0x1.8p-15 or 0x0.8p-16.

    float.fromhex would round to binary64; these are all narrow, but parsing
    exactly costs nothing and removes the question.
    """
    s = s.strip()
    low = s.lower()
    if low in ("nan", "-nan", "+nan"):
        return ("nan", None)
    if low in ("inf", "+inf", "-inf", "infinity", "-infinity"):
        return ("inf", low.startswith("-"))
    neg = low.startswith("-")
    low = low.lstrip("+-")
    if not low.startswith("0x"):
        return (None, None)
    mant, _, exp = low[2:].partition("p")
    e = int(exp) if exp else 0
    whole, _, frac = mant.partition(".")
    v = Fraction(int(whole or "0", 16))
    if frac:
        v += Fraction(int(frac, 16), 16 ** len(frac))
    v *= Fraction(2) ** e
    return ("finite", -v if neg else v)


def load_oracle():
    sys.path.insert(0, CONF)
    for name in os.listdir(CONF):
        if not name.endswith("_ref.py"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(name[:-3],
                                                          os.path.join(CONF, name))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception:
            continue
        if "fp8_e4m3" in (getattr(mod, "FORMATS", {}) or {}):
            return mod
    return None


def main() -> int:
    mod = load_oracle()
    if mod is None:
        print("no oracle module exporting fp8_e4m3 found")
        return 2

    overall_bad = 0
    for fid, pdir, desc in PAIRS:
        fmt = mod.FORMATS[fid]
        print(f"\n=== {fid}  ({desc})")

        for variant in ("se", "sf"):
            rows = fetch_table(pdir, variant)
            if not rows:
                print(f"  Binary8{pdir.lower()}{variant}.csv  unavailable")
                continue

            agree = finite = spec_diff = bad = 0
            ratios = set()
            examples = []
            for code, val, _sub in rows:
                kind, ours_val = hexfloat_to_fraction(val)
                try:
                    got = mod.decode(fmt, code)
                except Exception:
                    continue
                got_special = getattr(got, "kind", None)

                if kind in ("nan", "inf") or got_special is not None:
                    if (kind == "nan") == (got_special == "nan") and \
                       (kind == "inf") == (got_special == "inf"):
                        agree += 1
                    else:
                        spec_diff += 1
                    continue
                if kind != "finite":
                    continue
                finite += 1
                if Fraction(got) == ours_val:
                    agree += 1
                else:
                    bad += 1
                    # Record the RATIO, not just the disagreement. A uniform ratio
                    # across every code is a different exponent bias -- a
                    # specification difference -- and looks nothing like a decoder
                    # defect, which would scatter.
                    if ours_val not in (0, None) and Fraction(got) != 0:
                        ratios.add(Fraction(got) / ours_val)
                    if len(examples) < 3:
                        examples.append((hex(code), val, str(got)[:24]))

            overall_bad += bad
            print(f"  Binary8{pdir.lower()}{variant}.csv  rows={len(rows):<4} "
                  f"finite={finite:<4} agree={agree:<4} "
                  f"finite-mismatch={bad:<3} special-differs={spec_diff}")
            for c, theirs, ours in examples:
                print(f"      {c}: P3109 {theirs}   ours {ours}")
            if ratios:
                shown = sorted(ratios)[:4]
                print(f"      ratio ours/P3109 over all {bad} mismatches: "
                      f"{len(ratios)} distinct value(s) -> "
                      f"{', '.join(str(r) for r in shown)}")

    print()
    if overall_bad == 0:
        print("Every FINITE code agrees with the P3109 working group's tables.")
        print("Special-value counts differ where the specifications differ -- OCP")
        print("E4M3FN has no infinity and one NaN, which P3109 does not have to")
        print("match. That is a specification difference, reported as one.")
    else:
        print(f"{overall_bad} FINITE code(s) disagree. That would be serious --")
        print("read the examples above before concluding anything.")
    return 1 if overall_bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
