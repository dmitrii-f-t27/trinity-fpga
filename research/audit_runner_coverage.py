#!/usr/bin/env python3
"""Which runnable checks is no aggregate runner looking at?

Pass 290 found that research/run_all_gates.py globbed audit_* and witness_* and
nothing else, so sixteen verify_* scripts -- including verify_tier_e.py, the check
on the strongest claim in either paper -- had never been in any sweep. The runner
reported "70 scripts found" against a corpus of 86 and said nothing about the
difference.

That was found by looking. A prefix is a bad way to decide what gets run, and
noticing the next missing prefix by eye is a worse way. This asks the question
mechanically and keeps asking it.

WHAT COUNTS AS A CHECK
----------------------
A Python file with an `if __name__ == "__main__"` block. A library module with no
entry point is not a check that nobody runs, it is a library.

WHAT COUNTS AS COVERED
----------------------
Executed by ANY runner or gate, not only by the three aggregate runners. That
distinction is the whole accuracy of this file.

The first version looked only at run_all_gates, verify_corrections_package and
generate_vectors, and reported 189 uncovered scripts. Most of that number was
false. conformance/*_ref.py are executed by audit_selftest_sensitivity.py, which
globs them itself at run time; a gate that discovers its own inputs covers them
just as surely as a runner that names them. So every audit_/witness_/verify_
script's globs are collected too.

The SKIP table counts as covered. A script skipped for a stated reason is a
decision; a script nobody ever globbed is an accident, and those are what this
looks for.

NOT EVERY UNCOVERED SCRIPT IS A PROBLEM
---------------------------------------
apply_* mutate files and must be run deliberately. gen_*, generate_* and
regenerate_* produce artefacts. Those are reported in their own bucket rather than
as findings, because a number that folds them in would be mostly false -- the
failure this campaign has now split out of three separate tools.

Usage:  python3 research/audit_runner_coverage.py [--verbose]

Exits non-zero if a check with an entry point is reachable from no runner and is
not a mutator or generator.
"""
import ast
import glob
import io
import os
import re
import sys
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")

RUNNERS = {
    "run_all_gates.py": os.path.join(HERE, "run_all_gates.py"),
    "verify_corrections_package.py": os.path.join(
        HERE, "verify_corrections_package.py"),
    "generate_vectors.py": os.path.join(CONF, "generate_vectors.py"),
}

# Deliberately not gates. Reported apart, never as findings.
MUTATOR = re.compile(r"^(apply|patch)_")
GENERATOR = re.compile(r"^(gen|generate|regenerate|make|build)_")

# Conformance HOSTS. These drive the AX7203 over UART and compare against a golden;
# without a board attached they cannot run at all, so no software sweep can or
# should include them. Counting 100-odd of them as "checks nobody runs" would make
# this gate's number mostly false -- which is what the first version did.
HOST = re.compile(r"_ax7203\.py$|_conformance\.py$|^batch_flash|^frame_alignment")


def has_entry_point(path):
    try:
        tree = ast.parse(io.open(path, encoding="utf-8", errors="replace").read())
    except Exception:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            for sub in ast.walk(node.test):
                if isinstance(sub, ast.Name) and sub.id == "__name__":
                    return True
    return False


def code_strings(path):
    """String literals that are CODE, not prose.

    A substring search over the whole source counted a filename mentioned in a
    docstring as coverage. That made the gate vacuous -- this very file names
    verify_tier_e.py and audit_selftest_sensitivity.py in its opening paragraphs,
    so under that rule it "covered" them by talking about them. It reported 0
    uncovered and could not have reported anything else. A check that cannot fail
    is what pass 282 wrote audit_unconditional_pass.py to find, and I had just
    written one.

    The tokenizer separates them: a triple-quoted string at column 0 is a
    docstring, comments are comments, everything else is code.
    """
    out = []
    try:
        with open(path, "rb") as fh:
            toks = list(tokenize.tokenize(fh.readline))
    except Exception:
        return out
    for tok in toks:
        if tok.type != tokenize.STRING:
            continue
        if tok.start[1] == 0 and tok.string[:3] in ('"' * 3, "'" * 3):
            continue                      # module or function docstring
        out.append(tok.string.strip("\"'"))
    return out


def covered_by(path, strings):
    """Named as a code string, or matched by a glob pattern that is a code string.

    Only patterns ending in .py count as globs: a runner globbing "*.v" is not
    running Python checks, and letting that match would put every file back under
    one wildcard.
    """
    base = os.path.basename(path)
    for lit in strings:
        if lit == base or lit.endswith("/" + base):
            return True
        if lit.endswith(".py") and any(c in lit for c in "*?[") \
                and glob.fnmatch.fnmatch(base, os.path.basename(lit)):
            return True
    return False


def runs_python(path):
    """Does this script EXECUTE other Python, rather than merely read it?

    The distinction that makes this gate work at all. Version three treated every
    audit_/witness_/verify_ script as an executor, and several of them -- including
    THIS ONE -- glob "*.py" in order to read files. So it declared itself a runner,
    matched every script in the directory, and reported 0 uncovered. A gate that
    covers the corpus by scanning it is not covering anything.

    An executor spawns a Python subprocess: sys.executable in a subprocess call.
    audit_selftest_sensitivity does (it runs each oracle's self-test);
    audit_absolute_paths does not (it opens and greps).
    """
    try:
        src = io.open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return False
    return "sys.executable" in src and "subprocess" in src


def all_executors():
    """The aggregate runners, plus any gate that actually runs other Python.

    audit_selftest_sensitivity globbing conformance/*_ref.py and executing each is
    the case that matters: those nineteen oracles are exercised every sweep, by it,
    and calling them uncovered would be false.
    """
    out = dict(RUNNERS)
    me = os.path.basename(__file__)
    for p in (glob.glob(os.path.join(HERE, "audit_*.py"))
              + glob.glob(os.path.join(HERE, "witness_*.py"))
              + glob.glob(os.path.join(HERE, "verify_*.py"))):
        if os.path.basename(p) == me:
            continue                       # never let this file cover the corpus
        if runs_python(p):
            out.setdefault(os.path.basename(p), p)
    return out


def main():
    verbose = "--verbose" in sys.argv
    RUNNERS.update(all_executors())
    sources = {}
    for name, p in RUNNERS.items():
        sources[name] = code_strings(p) if os.path.exists(p) else []

    checks = sorted(glob.glob(os.path.join(HERE, "*.py"))
                    + glob.glob(os.path.join(CONF, "*.py")))
    entry, no_entry = [], []
    for p in checks:
        if os.path.basename(p) in RUNNERS:
            continue
        (entry if has_entry_point(p) else no_entry).append(p)

    # Coverage has two qualities and folding them loses the interesting one.
    #
    #   named or purposeful   a runner names the file, or globs a pattern that
    #                         describes what it is: "*_ref.py", "*_conformance_
    #                         ax7203.py". The gate knows what it is running.
    #
    #   wildcard only         the only thing reaching it is a bare "*.py". It is
    #                         swept, not chosen. audit_script_tree and
    #                         audit_reproducibility do this, and between them they
    #                         make every file in the corpus "covered".
    #
    # A bare wildcard covers everything and therefore distinguishes nothing: the
    # count cannot drop when a new check is added, so it cannot warn about one. The
    # files only a wildcard reaches are the ones a purposeful runner has never been
    # taught about, and that is the number worth watching.
    WILDCARD = ("*.py",)
    uncovered, mutators, generators, hosts, wildcard_only = [], [], [], [], []
    for p in entry:
        base = os.path.basename(p)
        purposeful = any(
            covered_by(p, [l for l in lits if l not in WILDCARD])
            for lits in sources.values())
        if purposeful:
            continue
        if any(covered_by(p, lits) for lits in sources.values()):
            wildcard_only.append(os.path.relpath(p, ROOT))
            continue
        if MUTATOR.match(base):
            mutators.append(base)
        elif GENERATOR.match(base):
            generators.append(base)
        elif HOST.search(base):
            hosts.append(base)
        else:
            uncovered.append(os.path.relpath(p, ROOT))

    print("python files in research/ and conformance/ : %d" % len(checks))
    print("   with an entry point (runnable checks)   : %d" % len(entry))
    print("   libraries, no entry point               : %d" % len(no_entry))
    print()
    print("REACHABLE FROM NO RUNNER            : %d" % len(uncovered))
    print("reached ONLY by a bare *.py wildcard : %d" % len(wildcard_only))
    for rel in wildcard_only[:12]:
        print("    %s" % rel)
    if len(wildcard_only) > 12:
        print("    ... and %d more (--verbose)" % (len(wildcard_only) - 12))
    if verbose:
        for rel in wildcard_only[12:]:
            print("    %s" % rel)
    print()
    print("A bare wildcard covers everything and distinguishes nothing: its count")
    print("cannot drop when a check is added, so it cannot warn about one. These")
    print("are the files no purposeful runner has been taught about.")
    print()
    for rel in uncovered:
        print("    %s" % rel)
    print()
    print("uncovered but deliberately so:")
    print("   mutators (apply_/patch_)   : %d   %s"
          % (len(mutators), ", ".join(mutators[:4])))
    print("   generators (gen_/regen_)   : %d   %s"
          % (len(generators), ", ".join(generators[:4])))
    print("   board hosts (need an AX7203): %d   %s"
          % (len(hosts), ", ".join(hosts[:3])))
    if verbose:
        for label, rows in (("mutators", mutators), ("generators", generators)):
            print("  %s:" % label)
            for b in rows:
                print("      %s" % b)
    print()
    if uncovered:
        print("Each of these has an entry point and no runner globs it. That is how")
        print("sixteen verify_* scripts sat outside every sweep until pass 290, and")
        print("how pass 250's retracted LUT table survived a pass.")
    else:
        print("every runnable check is reachable from a runner.")
    return 1 if uncovered else 0


if __name__ == "__main__":
    sys.exit(main())
