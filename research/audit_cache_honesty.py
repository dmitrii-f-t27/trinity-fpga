#!/usr/bin/env python3
"""Does the cache change any answer?

research/gate_cache.py exists so two slow gates get run at all. It buys that by
trusting a key. If the key misses an input, the gate reports last pass's verdict
as this pass's -- a green light that has stopped meaning anything, which is worse
than the timeout it replaced, because a timeout is visibly a timeout.

So the cache does not get to assert its own correctness. This runs each cached
gate twice -- once with --no-cache, once warm -- and requires the reports to be
identical line for line, except the cache's own summary line.

That is a check of THIS corpus at THIS moment, not a proof. It cannot find a key
that misses an input nothing has changed yet. What it does catch is the ordinary
failure: a gate whose verdict depends on something the key does not cover, on a
tree where that something is already varying.

Usage:  python3 research/audit_cache_honesty.py [--verbose]
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

GATES = [
    ("audit_yosys_reads.py", []),
    ("audit_selftest_sensitivity.py", []),
]


def run(script, extra):
    r = subprocess.run([sys.executable, os.path.join(HERE, script)] + extra,
                       capture_output=True, text=True, timeout=3600)
    # The summary line reports hits and misses, which differ BY DESIGN between a
    # cold and a warm run. Everything else must not.
    lines = [ln for ln in (r.stdout or "").splitlines()
             if not ln.startswith("cache")]
    return r.returncode, lines


def main():
    verbose = "--verbose" in sys.argv
    bad = 0
    for script, extra in GATES:
        path = os.path.join(HERE, script)
        if not os.path.exists(path):
            print("%-34s MISSING" % script)
            bad += 1
            continue
        cold_rc, cold = run(script, extra + ["--no-cache"])
        warm_rc, warm = run(script, extra)          # populates, then reuses
        again_rc, again = run(script, extra)        # the run that is fully warm

        same = (cold == warm == again) and (cold_rc == warm_rc == again_rc)
        print("%-34s %s   (rc %d/%d/%d, %d lines)"
              % (script, "agree" if same else "DISAGREE",
                 cold_rc, warm_rc, again_rc, len(cold)))
        if not same:
            bad += 1
            for a, b in zip(cold, again):
                if a != b:
                    print("     cold: %s" % a)
                    print("     warm: %s" % b)
            if len(cold) != len(again):
                print("     line count differs: %d cold, %d warm"
                      % (len(cold), len(again)))
        elif verbose:
            for ln in cold[:6]:
                print("     %s" % ln)

    print()
    print("cached gates whose answer the cache changed : %d" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
