#!/usr/bin/env python3
"""Run every audit and witness in this directory, and say which ones fail.

Forty passes have left 65 scripts here. Each was written to answer one question
and then, mostly, never run again -- and twice that cost something:

  * pass 242 made gfternary_ref.neg_zero raise and did not regenerate the packs
    whose specials legend still listed one. Two passes later the reproducibility
    audit caught it, by accident, while checking something else.
  * pass 250's LUT parser summed across a `stat` block boundary and produced a
    published table of deviations that did not exist. It survived a pass.

Both would have been caught the next day by running everything. So: one entry
point, a per-script timeout, and a report.

A script counts as failing only if it exits non-zero. Several are inventories
rather than gates and always exit 0; that is fine, they are still exercised, and
a crash in one shows up as a non-zero exit like any other.

Usage:  python3 research/run_all_gates.py [--timeout N] [--jobs N] [--verbose]
"""
import concurrent.futures
import glob
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Scripts that need a board, a network, or hours of synthesis. Excluded with the
# reason attached rather than silently skipped.
SKIP = {
    "audit_yosys_synth.py": "hours of synthesis -- run it deliberately",
    "audit_build_matrix_path.py": "hours of synthesis -- run it deliberately",
    "witness_gf_adder_rtl.py": "minutes per format under iverilog",
    "run_all_gates.py": "this script",
    # Runs two gates three times each, twice of them cold, on purpose. It is the
    # check on the cache that lets those two gates finish here at all, and it is
    # slower than both of them put together -- which is correct: the fast path
    # earns its speed by being compared against the slow one somewhere.
    "audit_cache_honesty.py": "runs the cached gates cold to compare -- run it deliberately",
    # Re-runs six of the gates in this very sweep, two of them synthesising. Inside
    # the sweep it would duplicate them and treat their exit codes by a DIFFERENT
    # convention -- HOLDS/WITHDRAWN rather than clean/findings. Two conventions in
    # one number is the fold this whole series keeps splitting apart.
    "verify_corrections_package.py": "re-runs six gates under a different exit-code convention",
}


def run_one(path, timeout):
    name = os.path.basename(path)
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, path], cwd=ROOT,
                           capture_output=True, text=True, timeout=timeout)
        rc = r.returncode
        tail = (r.stdout + r.stderr).strip().splitlines()
        note = tail[-1][:90] if tail else ""
    except subprocess.TimeoutExpired:
        return name, "TIMEOUT", time.time() - t0, "exceeded %ds" % timeout
    except Exception as e:                                # noqa: BLE001
        return name, "ERROR", time.time() - t0, type(e).__name__
    # These scripts use exit codes with a meaning, and flattening them into
    # pass/fail produces a number that is mostly false -- the trap this series
    # has criticised three times and would otherwise walk into here.
    #   0  ran, nothing to report
    #   1  ran, HAS findings. Several are inventories that always find something
    #   2  could not run: needs an argument, a URL, or gh access
    status = {0: "clean", 1: "findings", 2: "needs input"}.get(rc, "CRASH rc=%d" % rc)
    return name, status, time.time() - t0, note


def main():
    verbose = "--verbose" in sys.argv
    timeout = 180
    jobs = 4
    if "--timeout" in sys.argv:
        timeout = int(sys.argv[sys.argv.index("--timeout") + 1])
    if "--jobs" in sys.argv:
        jobs = int(sys.argv[sys.argv.index("--jobs") + 1])

    # verify_* too. The first version globbed audit_* and witness_* only, so
    # SIXTEEN verify_* scripts -- including verify_tier_e.py, which is the check on
    # the strongest claim in either paper -- had never been in any sweep. The
    # runner reported "70 scripts found" against a corpus of 86 and said nothing
    # about the difference, which is the same shape as a gate that does not run.
    paths = sorted(glob.glob(os.path.join(HERE, "audit_*.py"))
                   + glob.glob(os.path.join(HERE, "witness_*.py"))
                   + glob.glob(os.path.join(HERE, "verify_*.py")))
    todo = [p for p in paths if os.path.basename(p) not in SKIP]

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = [ex.submit(run_one, p, timeout) for p in todo]
        for f in concurrent.futures.as_completed(futs):
            results.append(f.result())

    order = {"CRASH": 0, "TIMEOUT": 1, "ERROR": 1, "needs input": 2,
             "findings": 3, "clean": 4}
    results.sort(key=lambda r: (order.get(r[1].split(" rc=")[0], 0), r[0]))
    crashed = [r for r in results if r[1].startswith(("CRASH", "ERROR"))]
    slow = [r for r in results if r[1] == "TIMEOUT"]
    needs = [r for r in results if r[1] == "needs input"]
    found = [r for r in results if r[1] == "findings"]
    clean = [r for r in results if r[1] == "clean"]

    print("scripts found   : %d" % len(paths))
    print("skipped         : %d" % (len(SKIP) - 1))
    print("run             : %d" % len(todo))
    print()
    print("  CRASHED or errored : %d   <- the only category that means a regression"
          % len(crashed))
    print("  timed out          : %d   (raise --timeout)" % len(slow))
    print("  need an argument   : %d   (tools, not gates)" % len(needs))
    print("  ran, have findings : %d   (inventories report by design)" % len(found))
    print("  ran, nothing found : %d" % len(clean))
    print()
    for name, status, secs, note in results:
        if status in ("clean",) and not verbose:
            continue
        print("%-40s %-12s %5.1fs  %s" % (name[:40], status, secs, note[:70]))
    if not verbose:
        print()
        print("(--verbose also lists the %d that ran clean)" % len(clean))
    print()
    for name, why in sorted(SKIP.items()):
        if name != "run_all_gates.py":
            print("skipped %-34s %s" % (name, why))
    return 1 if crashed else 0


if __name__ == "__main__":
    sys.exit(main())
