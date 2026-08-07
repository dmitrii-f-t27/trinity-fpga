#!/usr/bin/env python3
"""Re-check all ten items of the corrections package at once.

Pass 287 finished giving every item an executable check. Ten tools written across
passes 248-287 and never once run together -- which is precisely the state pass 275
found the 65 gates in, and the state that let pass 250's retracted LUT table and
three stale gfternary packs survive.

EXIT CODES MEAN OPPOSITE THINGS HERE
------------------------------------
This is the whole reason the runner is not a for-loop over `subprocess.run`.

    audit_cite_keys        exit 1 = unresolved keys found = THE ITEM HOLDS
    audit_dsp_inference    exit 1 = DSPs inferred         = THE ITEM HOLDS
    audit_additional_cores exit 1 = a core deviates       = THE ITEM HOLDS
    audit_cost_model       exit 1 = a subset DOES fit     = THE ITEM IS DEAD
    audit_gf64_chain       exit 1 = a complete chain      = THE ITEM IS DEAD

Flattening those into pass/fail produces a number that is roughly half false --
the exact failure pass 275's first gate runner nearly shipped and pass 278 had to
split out of audit_yosys_reads. Each item therefore declares which exit code means
its finding still stands, and this reports HOLDS / WITHDRAWN / BROKEN, never
"pass".

    HOLDS      the tool ran and its finding is still true
    WITHDRAWN  the tool ran and says the finding no longer applies -- go read it,
               the package needs editing
    BROKEN     the tool crashed, timed out, or could not run. Says nothing about
               the item either way, and must never be read as either.

Usage:  python3 research/verify_corrections_package.py [--timeout S] [--fast]

--fast skips the two items that synthesise (4 and 6), which take minutes.

Exits non-zero if any item is WITHDRAWN or BROKEN.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# (item, one-line subject, argv, exit code that means THE FINDING STILL HOLDS, slow)
ITEMS = [
    ("1", "GF64 has no complete Tier-E chain",
     ["research/audit_gf64_chain.py"], 0, False),
    ("2,3", "the arithmetic claims recompute",
     ["research/audit_arithmetic_claims.py"], None, False),
    ("4", "the flag rule leaves DSPs inferable",
     ["research/audit_dsp_inference.py", "--per-op", "2", "--timeout", "300"],
     1, True),
    ("5", "no subset fits c=1.63 with R2>=0.97",
     ["research/audit_cost_model.py"], 0, False),
    ("6", "GF Quire does not reproduce",
     ["research/audit_additional_cores.py"], 1, True),
    ("7,10", "seven workloads, seven formats",
     ["research/workload_suite.py"], None, False),
    ("8", "the E8M0 oracle and packs exist",
     ["conformance/e8m0_ref.py"], 0, False),
    ("9", "three cite keys resolve to nothing",
     ["research/audit_cite_keys.py"], 1, False),
]


def run(argv, timeout):
    try:
        r = subprocess.run([sys.executable] + argv, cwd=ROOT,
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "timed out at %ds" % timeout
    except Exception as e:
        return None, str(e)[:70]
    tail = [l for l in (r.stdout or "").splitlines() if l.strip()]
    return r.returncode, (tail[-1][:62] if tail else "(no output)")


def main():
    timeout = 1800
    fast = "--fast" in sys.argv
    if "--timeout" in sys.argv:
        timeout = int(sys.argv[sys.argv.index("--timeout") + 1])

    print("%-6s %-38s %-10s %s" % ("item", "subject", "verdict", "last line"))
    holds, withdrawn, broken, skipped, informational = [], [], [], [], []
    for item, subject, argv, want, slow in ITEMS:
        if fast and slow:
            skipped.append((item, "synthesises -- run without --fast"))
            print("%-6s %-38s %-10s %s" % (item, subject[:38], "skipped",
                                           "slow, --fast"))
            continue
        if not os.path.exists(os.path.join(ROOT, argv[0])):
            broken.append((item, "tool missing: %s" % argv[0]))
            print("%-6s %-38s %-10s %s" % (item, subject[:38], "BROKEN",
                                           "tool missing"))
            continue
        rc, last = run(argv, timeout)
        if rc is None:
            broken.append((item, last))
            verdict = "BROKEN"
        elif want is None:
            # No declared meaning, because the item is not a falsifiable finding:
            # item 2 is a wording point whose body is already correct, item 3 is a
            # sensitivity note, and 7/10 produce tables rather than verdicts. Their
            # tools recompute and print; they cannot say "still true".
            #
            # So these are counted APART. Folding them into the HOLDS number would
            # report 8 verified items when 6 are verified and 2 merely ran -- the
            # same fold this runner exists to avoid, one level up.
            verdict = "BROKEN" if rc >= 2 else "ran"
            (broken if rc >= 2 else informational).append((item, last))
        elif rc == want:
            verdict = "HOLDS"
            holds.append((item, last))
        else:
            verdict = "WITHDRAWN"
            withdrawn.append((item, "exit %d, expected %d -- %s" % (rc, want, last)))
        print("%-6s %-38s %-10s %s" % (item, subject[:38], verdict, last))

    print()
    print("items whose finding still HOLDS : %d   (a declared verdict)" % len(holds))
    print("items that ran, no verdict to give : %d   (not falsifiable -- 2,3 and 7,10)"
          % len(informational))
    print("items reported WITHDRAWN        : %d   <- the package needs editing"
          % len(withdrawn))
    print("checks BROKEN                   : %d   <- says nothing about the item"
          % len(broken))
    if skipped:
        print("skipped                         : %d" % len(skipped))
    print()
    for label, rows in (("WITHDRAWN", withdrawn), ("BROKEN", broken)):
        if rows:
            print("%s:" % label)
            for item, why in rows:
                print("    item %-5s %s" % (item, why))
            print()
    if not withdrawn and not broken:
        print("every checked item still holds. This re-checks the FINDINGS, not")
        print("the papers: a finding that holds means the discrepancy is still")
        print("there, not that anything has been submitted or fixed.")
    return 1 if (withdrawn or broken) else 0


if __name__ == "__main__":
    sys.exit(main())
