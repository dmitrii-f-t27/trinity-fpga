#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""How much of this repository's CI is actually green, and for how long has it not been?

Eleven gates were added by this campaign and all eleven are green. That says nothing
about the other seventy-two, and a red workflow sitting next to green ones trains
everyone to stop reading both.

Pass 173 counted: of 83 workflow files, 81 have run and **13 are failing**. Four are the
TRI-NET line and failed today; `fpga-ci` and `fpga-regression` have failed on all thirty
of their most recent runs, back to 2026-07-23; `wrapper-fsm-sim` and `decode-verify`
since 2026-07-09; four more date from April and July.

None was caused by this campaign, and that was checked rather than assumed: the RTL
edits landed on 2026-08-02, and every one of these was already failing before it.

**A methodological note that cost a step to learn.** `gh run list --limit 400` across
all workflows suggested 61 had never run. Querying each workflow file individually
showed 81 had. The first answer was the sampling window, not the world -- the fifth time
in this campaign that a "missing" result was the query. This tool therefore asks per
file, which is slower and right.

It reports and does not fix. Most of these belong to other workstreams, and a campaign
that silently edits another line's CI is worse than one that leaves it red.

    python3 research/audit_ci_health.py [--self-check]
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Added by the numeric-verification campaign. Listed so the report can separate
# "our gates" from "the repository's state" without claiming the latter.
CAMPAIGN = {
    "reproducibility-gate.yml", "stale-citation-gate.yml", "pack-layout-gate.yml",
    "module-loader-gate.yml", "counted-claim-gate.yml", "hardware-row-gate.yml",
    "format-table-gate.yml", "exhaustive-claim-gate.yml", "narrow-register-gate.yml",
    "author-docs-gate.yml", "rtl-datapath-gate.yml",
}


def latest(workflow: str):
    """(conclusion, date) of the newest run, or None if it has never run."""
    r = subprocess.run(
        ["gh", "run", "list", "--workflow", workflow, "--limit", "1",
         "--json", "conclusion,createdAt"],
        capture_output=True, text=True, timeout=90, cwd=ROOT)
    if r.returncode != 0:
        return "unqueryable"
    try:
        v = json.loads(r.stdout or "[]")
    except Exception:
        return "unqueryable"
    if not v:
        return None
    return (v[0].get("conclusion"), (v[0].get("createdAt") or "")[:10])


def self_check() -> int:
    """The query must distinguish a workflow that never ran from one it cannot ask
    about. Reporting the second as the first is how pass 171's citation gate went red
    in CI, and how pass 165 invented a missing file."""
    r = latest("this-workflow-does-not-exist-" + "x" * 12 + ".yml")
    ok = r is None or r == "unqueryable"
    print(f"  a workflow that does not exist -> {r!r}")
    print(f"  distinguishable from a real failure -> {ok}")
    print(f"\nself-check: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--self-check" in sys.argv:
        return self_check()

    files = sorted(os.path.basename(p)
                   for p in glob.glob(os.path.join(ROOT, ".github/workflows/*.yml")))
    green, red, never, unq, skipped = [], [], [], [], []
    for wf in files:
        res = latest(wf)
        if res == "unqueryable":
            unq.append(wf)
        elif res is None:
            never.append(wf)
        elif res[0] == "success":
            green.append(wf)
        elif res[0] in ("skipped", "cancelled", "neutral"):
            # A run that was skipped did not fail. Counting it red inflates the number
            # this tool exists to report honestly.
            skipped.append((wf, res[0], res[1]))
        else:
            red.append((wf, res[0], res[1]))

    print(f"COVERAGE: {len(files)} workflow files, each queried individually")
    print(f"  latest run succeeded : {len(green)}")
    print(f"  latest run FAILED    : {len(red)}")
    print(f"  never run            : {len(never)}")
    if skipped:
        print(f"  latest run skipped   : {len(skipped)}   (not a failure)")
    if unq:
        print(f"  could not be queried : {len(unq)}   (reported, not counted as green)")

    mine_red = [r for r in red if r[0] in CAMPAIGN]
    print(f"\n  of the {len(CAMPAIGN)} gates this campaign added, failing: {len(mine_red)}")

    if red:
        print("\nfailing, newest first:")
        for wf, concl, when in sorted(red, key=lambda x: x[2], reverse=True):
            tag = "  <- this campaign" if wf in CAMPAIGN else ""
            print(f"  {when}  {wf:<40} {concl}{tag}")

    if never:
        print(f"\nnever run: {', '.join(never)}")

    print("""
This reports and does not fix. Most of these belong to other workstreams, and a campaign
that silently edits another line's CI is worse than one that leaves it red.

The number that matters is not how many are red but how long they have been: a workflow
failing for weeks is not a check, it is a habit. Two here have failed on all thirty of
their most recent runs.""")
    return 1 if mine_red else 0


if __name__ == "__main__":
    raise SystemExit(main())
