#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Add each workflow the path of the script it runs. Nine one-line edits.

`research/audit_workflow_paths.py` has reported since pass 184 that nine workflows run a
tracked script no `paths:` pattern watches. Fixing the script therefore does not trigger
the workflow that executes it, and the job keeps re-running whatever version last happened
to touch a watched file. Pass 183's fix to `conformance/wrapper_fsm_audit.py` had to be
dispatched by hand for exactly this reason.

Editing `.github/workflows/` is blocked for this session at the tool level, so the change
ships as a script you run yourself:

    python3 research/apply_workflow_paths.py            # show the diff, change nothing
    python3 research/apply_workflow_paths.py --write    # apply it

It is additive. Widening a `paths:` filter can make a job run more often and can never
make it run less, nor change what it does when it runs.
"""
from __future__ import annotations

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WF = os.path.join(ROOT, ".github", "workflows")

FIX = {
    "ax7203-trinet-node-v2.yml": ["conformance/trinet_mac32_conformance_ax7203.py"],
    "conformance-frame-alignment.yml": [
        "conformance/frame_alignment_check.py",
        "conformance/gfternary_compute_conformance_ax7203.py",
        "conformance/trinet_mac32_conformance_ax7203.py"],
    "conformance-selftest.yml": [
        "conformance/compute_golden_consistency.py",
        "conformance/corona_decode_host_ax7203.py",
        "conformance/golden_consistency.py"],
    "lut-report.yml": ["fpga/openxc7-synth/run_synth.py"],
    "module-loader-gate.yml": ["research/audit_module_loaders.py"],
    "reproducibility-gate.yml": ["research/audit_reproducibility.py"],
    "stale-citation-gate.yml": ["research/audit_stale_citations.py"],
    "trinet-portability.yml": ["conformance/portability_check.py"],
    "wrapper-fsm-sim.yml": ["conformance/wrapper_fsm_audit.py"],
}


def patched(path, scripts):
    """The file with the paths added after the first `paths:` block, or None."""
    lines = io.open(path, encoding="utf-8").read().split("\n")
    out, done, in_paths = [], False, False
    for line in lines:
        if re.match(r"\s*paths:\s*$", line):
            in_paths = True
            out.append(line)
            continue
        if in_paths and not re.match(r"\s*-\s*['\"]", line):
            if not done:
                indent = re.match(r"(\s*)", out[-1]).group(1)
                out.append(f"{indent}# the scripts this job runs: "
                           f"fixing a check must re-run it")
                for s in scripts:
                    out.append(f"{indent}- '{s}'")
                done = True
            in_paths = False
        out.append(line)
    return "\n".join(out) if done else None


def main() -> int:
    write = "--write" in sys.argv
    changed = skipped = 0
    for name, scripts in FIX.items():
        path = os.path.join(WF, name)
        if not os.path.exists(path):
            print(f"  {name}: absent, skipped")
            skipped += 1
            continue
        before = io.open(path, encoding="utf-8").read()
        if all(f"'{s}'" in before for s in scripts):
            print(f"  {name}: already watches its scripts")
            continue
        after = patched(path, scripts)
        if after is None:
            print(f"  {name}: no `paths:` block found, skipped")
            skipped += 1
            continue
        changed += 1
        print(f"  {name}: + {len(scripts)} path(s)")
        for s in scripts:
            print(f"      - '{s}'")
        if write:
            io.open(path, "w", encoding="utf-8").write(after)

    print(f"\n  {changed} workflows {'updated' if write else 'would change'}, "
          f"{skipped} skipped")
    if not write:
        print("  re-run with --write to apply")
    else:
        print("  verify with: python3 research/audit_workflow_paths.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
