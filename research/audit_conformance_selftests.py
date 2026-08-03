#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run every conformance host's self-test, and require them all to pass.

Until pass 181 this could not exist. Thirty of these hosts imported `serial` at module
level even though their golden models need no serial port, so they could not be imported
-- let alone self-tested -- anywhere pyserial was absent, including CI. Moving the import
into the functions that open a port freed 30 goldens; this is what that buys.

Sixty-four hosts offer `--self-test`. Each checks its golden decode model against
hand-derived or authoritative vectors, needing no board and no driver. Sixty-four
verified decode models, none of which was checked automatically before.

What a self-test is and is not
------------------------------
It compares a host's golden model against vectors, on this machine. It does NOT touch
the board, and passing it is not a Tier-E result and never contributes to one -- that
needs a public CI run, a bitstream SHA-256, a UART log at 160000 baud and a matching
IDCODE, and simulation is explicitly none of the four.

What it does catch is a golden that has drifted from the vectors it claims to match,
which is the failure that would make a board run agree with the wrong answer.

What CI covers today, and what it could
---------------------------------------
`.github/workflows/conformance-selftest.yml` exists and is green. Its step is called
"Run all conformance golden self-tests" and runs **eight** of the sixty-four: one decode
host and seven `gf*_add` compute hosts, plus two cross-host consistency scripts. The
name overstates the coverage eightfold.

That was not carelessness -- it could not have run the rest. Until pass 181 thirty of
these hosts could not be imported without pyserial, which CI does not install.

Replacing the eight hand-listed invocations with

    python3 research/audit_conformance_selftests.py --self-check
    python3 research/audit_conformance_selftests.py

takes that workflow from 8 to 64 and keeps the two consistency scripts as their own
step. This campaign does not edit other workstreams' workflows, so the change is
recorded here rather than made.

    python3 research/audit_conformance_selftests.py [--self-check]
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")

# Hosts whose self-test needs an argument to select what it checks. Recorded with the
# argument rather than skipped: skipping one of sixty-four would be invisible in a
# summary line, and this file exists because invisible gaps are the recurring defect.
EXTRA_ARGS = {
    "gf16_compute_conformance_ax7203.py": ["--op", "add"],
}


def hosts() -> list[str]:
    out = []
    for p in sorted(glob.glob(os.path.join(CONF, "*_conformance_ax7203.py"))):
        if "--self-test" in open(p, encoding="utf-8", errors="replace").read():
            out.append(p)
    return out


def self_check() -> int:
    """A gate that runs nothing looks the same as a gate that passes everything.

    The failure mode this guards against is the glob matching zero files -- a rename,
    a moved directory, a typo in the pattern -- after which this would report a clean
    sweep of nothing at all.
    """
    n = len(hosts())
    ok = n >= 50
    print(f"  hosts discovered: {n}")
    print(f"  enough to be a real sweep (>= 50) -> {ok}")
    print(f"\nself-check: {'PASS' if ok else 'FAIL — the glob found almost nothing'}")
    return 0 if ok else 1


def main() -> int:
    if "--self-check" in sys.argv:
        return self_check()

    found = hosts()
    passed, failed = [], []
    for p in found:
        name = os.path.basename(p)
        cmd = [sys.executable, p, "--self-test"] + EXTRA_ARGS.get(name, [])
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                               cwd=ROOT)
        except subprocess.TimeoutExpired:
            failed.append((name, "timed out"))
            continue
        if r.returncode == 0:
            passed.append(name)
        else:
            tail = ((r.stdout or "") + (r.stderr or "")).strip().split("\n")
            failed.append((name, (tail[-1] if tail else "")[:70]))

    print(f"COVERAGE: {len(found)} conformance hosts offering --self-test")
    print(f"  passing : {len(passed)}")
    print(f"  failing : {len(failed)}")
    if EXTRA_ARGS:
        print(f"  needing an argument, supplied here: "
              f"{', '.join(sorted(EXTRA_ARGS))}")

    for name, why in failed:
        print(f"\n  FAIL  {name}")
        print(f"        {why}")

    print("""
A self-test compares a host's golden model against its vectors, on this machine. It
does NOT touch the board, and passing is not a Tier-E result and never contributes to
one -- that needs a public CI run, a bitstream SHA-256, a UART log at 160000 baud and a
matching IDCODE, and simulation is none of the four.

What it catches is a golden that has drifted from the vectors it claims to match, which
is the failure that would make a board run agree with the wrong answer.""")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
