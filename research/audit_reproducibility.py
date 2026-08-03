#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Would these checks work for anyone else?

Pass 169 found six checks hardcoding a path that contains a session identifier. Every
result they produced -- the posit cross-validation against SoftPosit, the takum8
regeneration ledger, the lns representation-error measurement -- was reproducible only
from inside the session that wrote them.

**The sweep that should have caught it did not.** Running everything in a clean tree
found nothing, because the path still existed on the machine doing the running. A
defect that only appears somewhere else is invisible from here, and that is what took
169 passes.

So this does not look for the defect. It reproduces the condition: point
`$TRINITY_ARTEFACTS` at an empty directory and run every check that resolves an
artefact through `research/artefacts.py`. Each must

    exit 2, and print how to obtain what it is missing

Exit 0 is the failure. A check that passes without its input is claiming a result it did
not compute, and no amount of reading its output would reveal that -- the output looks
like every other clean run.

Two things this deliberately does NOT do. It does not fetch anything, because a suite
that downloads its own evidence cannot be audited by reading it. And it does not require
a check to succeed, because succeeding needs artefacts this gate has just taken away.

    python3 research/audit_reproducibility.py [--self-check]
"""
from __future__ import annotations

import glob
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# A check depends on an artefact if it resolves one through the shared helper.
USES_HELPER = re.compile(r"from\s+artefacts\s+import|import\s+artefacts\b")

# The session-scoped path that started this. Nothing outside artefacts.py may carry it.
SESSION_PATH = re.compile(r"/private/tmp/claude-\d+/")

# What a missing-input message must contain to be useful to a stranger.
HELPFUL = re.compile(
    r"gh api|iverilog|build |see research/|--artefacts|TRINITY_ARTEFACTS|"
    r"pip install",                       # a missing DEPENDENCY is also a missing
    re.I)                                 # input, and needs the same courtesy


def dependents() -> list[str]:
    out = []
    for p in sorted(glob.glob(os.path.join(HERE, "*.py"))):
        if os.path.basename(p) in ("artefacts.py", os.path.basename(__file__)):
            continue
        if USES_HELPER.search(open(p, encoding="utf-8", errors="replace").read()):
            out.append(p)
    return out


def hardcoders() -> list[str]:
    out = []
    for p in sorted(glob.glob(os.path.join(HERE, "*.py"))):
        if os.path.basename(p) == "artefacts.py":
            continue                      # documented legacy fallback lives there
        if SESSION_PATH.search(open(p, encoding="utf-8", errors="replace").read()):
            out.append(p)
    return out


def self_check() -> int:
    """The gate must reject a check that ignores the empty directory.

    Written as a temporary file rather than a real one: a check that always passes is
    exactly what this gate exists to catch, and it should be able to catch a fake.
    """
    src = ("import sys\n"
           "sys.path.insert(0, %r)\n"
           "from artefacts import artefact_dir\n"
           "print('pretending to work in', artefact_dir())\n"
           "raise SystemExit(0)\n" % HERE)
    with tempfile.TemporaryDirectory() as td:
        fake = os.path.join(td, "always_passes.py")
        open(fake, "w").write(src)
        empty = os.path.join(td, "empty")
        os.makedirs(empty)
        env = dict(os.environ, TRINITY_ARTEFACTS=empty)
        r = subprocess.run([sys.executable, fake], capture_output=True, text=True,
                           timeout=120, env=env, cwd=ROOT)
        caught = r.returncode != 2
        print(f"  a check that exits 0 without its input is rejected -> {caught}")
    print(f"\nself-check: {'PASS' if caught else 'FAIL'}")
    return 0 if caught else 1


def main() -> int:
    if "--self-check" in sys.argv:
        return self_check()

    bad_paths = hardcoders()
    checks = dependents()

    print(f"COVERAGE: {len(checks)} artefact-dependent checks, run against an empty "
          f"artefact directory")
    print(f"  checks hardcoding a session path : {len(bad_paths)}\n")
    for p in bad_paths:
        print(f"  SESSION PATH  {os.path.relpath(p, ROOT)}")
        print(f"                will not resolve for anyone else, or in another session")

    failures = []
    with tempfile.TemporaryDirectory() as empty:
        env = dict(os.environ, TRINITY_ARTEFACTS=empty)
        for p in checks:
            name = os.path.basename(p)
            try:
                r = subprocess.run([sys.executable, p], capture_output=True, text=True,
                                   timeout=180, env=env, cwd=ROOT)
            except subprocess.TimeoutExpired:
                failures.append((name, "timed out"))
                continue
            out = (r.stdout or "") + (r.stderr or "")
            if r.returncode != 2:
                failures.append((name, f"exit {r.returncode}, expected 2"))
            elif not HELPFUL.search(out):
                failures.append((name, "exit 2 but no instruction for obtaining it"))
            else:
                print(f"  ok    {name:<34} exits 2 and says how to get its input")

    if failures:
        print()
        for name, why in failures:
            print(f"  FAIL  {name:<34} {why}")

    print(f"\nchecks that would mislead a stranger: {len(failures) + len(bad_paths)}")
    print("""
Exit 0 without an input is the failure. Such a check reports a result it did not
compute, and its output is indistinguishable from a real one -- which is why pass 169's
defect survived 169 passes and a full clean-tree sweep. Reproducing the condition is the
only way to see it from here.""")
    return 1 if (failures or bad_paths) else 0


if __name__ == "__main__":
    raise SystemExit(main())
