#!/usr/bin/env python3
"""Can yosys read every Verilog file in the synthesis tree?

Pass 237 built a parse guard on iverilog and pass 244 found what that could not
see: 30 files carrying `{0'b0, q_result}`, which iverilog accepts and yosys
rejects as an illegal zero-width constant. All 30 passed the guard and none could
be synthesised.

Pass 244 checked eight files with yosys and found a class of thirty. This asks the
same question of all 3,594.

`read_verilog` is the whole check here, deliberately. It is the front end the
synthesis flow actually uses, it costs about 40ms a file, and it is what catches
language-level defects. Full `synth_xilinx` is another matter -- two seconds and
up per file -- and research/synth_check.py does that for the files a change
touched.

Errors are grouped by their message rather than listed one per line, because a
tree this size fails in classes, not individually.

WHAT "CANNOT READ" MEANS, AND WHAT IT DOES NOT
----------------------------------------------
This gate first reported a single number: 22 sources yosys cannot read. That was
true of yosys's exit code and false about the tree. Three different things were in
it:

    15   a real parse defect -- yosys cannot read the Verilog
     5   $readmemb could not open a .mem file. The design parsed fine; a weights
         file is absent, or named relative to a directory yosys was not run from
     1   the file executed $finish in an elaboration-time initial block, which is
         what a self-checking file does. A testbench the name heuristic missed

Only the first is a defect, and only the first fails this gate. A number that
folds the other two in changes whenever someone moves a .mem file, and a gate
whose number moves for reasons unrelated to its subject stops being read -- which
is how pass 250's LUT table survived a pass and how pass 275's runner nearly
shipped "20 failures" that were mostly inventories.

Usage:  python3 research/audit_yosys_reads.py [--verbose] [--jobs N] [--no-cache]

Exits non-zero only on a parse defect.
"""
import collections
import concurrent.futures
import glob
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_cache                                                  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SYNTH = os.path.join(ROOT, "fpga", "openxc7-synth")

ERR = re.compile(r"^(?:.*?:\d+:\s*)?ERROR:\s*(.*)$", re.M)
# Strip file-specific detail so two instances of one defect land in one bucket.
NUM = re.compile(r"\b\d+\b")
QUOTED = re.compile(r"[`'\"]([^`'\"]*)[`'\"]")


def classify(msg):
    m = QUOTED.sub("<name>", msg)
    m = NUM.sub("<n>", m)
    return m.strip()[:110]


# A testbench is not a synthesis target. $display, $fopen and $readmemb are what
# testbenches are FOR, and yosys refusing them says nothing about the design.
# Counting those as failures would make the number mostly false, which is the way
# a guard stops being read -- the same trap pass 243 had to pull the zero-sign
# lint out of.
# Not every refusal is a defect in the Verilog.
#
#   $readmemb cannot open its file   the design parsed. A weights file is absent or
#                                    is named relative to a directory yosys was not
#                                    run from. Nothing about the RTL is wrong, and
#                                    counting it as a parse defect means the number
#                                    changes when someone moves a .mem.
#
#   $finish / $stop executed         the file ran an elaboration-time initial block
#                                    and halted on purpose. That is what a
#                                    self-checking file DOES; it is a testbench whose
#                                    name the heuristic below did not match.
#
# Both were in the 22 this gate reported as "sources yosys cannot read" -- a number
# that was true of yosys's exit code and false about the tree.
DATA_ERR = re.compile(r"Can not open file .* for .?\$readmem", re.I)
HALT_ERR = re.compile(r"System task .?\$(finish|stop).? executed", re.I)


def kind_of(err):
    if DATA_ERR.search(err):
        return "data"
    if HALT_ERR.search(err):
        return "halt"
    return "defect"


def is_testbench(path):
    b = os.path.basename(path)
    return (b.endswith("_tb.v") or b.startswith("tb_") or "_testbench" in b
            or b.endswith("_test.v") or re.search(r"_tb\d*\.v$", b) is not None)


def read_one(path):
    r = subprocess.run(["yosys", "-p", "read_verilog %s" % path],
                       capture_output=True, text=True)
    if r.returncode == 0:
        return path, None
    out = r.stdout + r.stderr
    hits = ERR.findall(out)
    return path, (hits[0].strip() if hits else out.strip().splitlines()[-1][:120])


def main():
    verbose = "--verbose" in sys.argv
    jobs = 6
    if "--jobs" in sys.argv:
        jobs = int(sys.argv[sys.argv.index("--jobs") + 1])
    files = sorted(glob.glob(os.path.join(SYNTH, "*.v")))
    if not files:
        print("no Verilog under %s" % SYNTH)
        return 2

    # 3,594 files at ~40ms each is past run_all_gates.py's budget, so this gate
    # timed out rather than ran -- and a gate that does not run is not a gate.
    # `read_verilog <file>` takes no include path and no libdir, so that file's
    # bytes plus the yosys version ARE the whole input, and a verdict keyed on
    # them cannot go stale. --no-cache re-derives everything; the two must agree,
    # which research/audit_cache_honesty.py checks.
    cache = gate_cache.Cache("yosys_reads", enabled="--no-cache" not in sys.argv)
    ver = gate_cache.tool_version(["yosys", "-V"])

    todo, results = [], {}
    for p in files:
        key = gate_cache.sha_files([p]) + "|" + ver
        # Unit is the basename, not the absolute path: every file here lives in one
        # directory so basenames are unique, and a cache keyed on absolute paths is
        # useless the moment the tree is checked out anywhere else. It is still
        # per-checkout in practice -- .gate_cache/ is ignored, so a fresh worktree
        # starts cold -- but nothing about the key stops it being carried.
        hit = cache.get(os.path.basename(p), key)
        if hit is None:
            todo.append((p, key))
        else:
            results[p] = hit["value"]

    failed, tb_failed = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        for path, err in ex.map(read_one, [p for p, _ in todo]):
            results[path] = err
    for p, key in todo:
        cache.put(os.path.basename(p), key, results[p])
    cache.save()

    defects, missing_data, halted, tb_failed = [], [], [], []
    for path in files:
        err = results.get(path)
        if not err:
            continue
        row = (os.path.basename(path), err)
        if is_testbench(path):
            tb_failed.append(row)
        else:
            kind = kind_of(err)
            {"defect": defects, "data": missing_data, "halt": halted}[kind].append(row)

    buckets = collections.defaultdict(list)
    for base, err in defects:
        buckets[classify(err)].append(base)

    tbs = sum(1 for f in files if is_testbench(f))
    print("files under fpga/openxc7-synth : %d  (%d of them testbenches)"
          % (len(files), tbs))
    print("%s" % cache.summary())
    print()
    # One number for "yosys cannot read it" put a parse defect, an absent data file
    # and a self-halting file in the same bucket, and the first version of this gate
    # reported all 22 as though they were the same thing. They are not: only the
    # first is a defect in the Verilog. Reporting them together is the
    # number-that-is-mostly-true failure this campaign keeps finding in its own
    # tools -- pass 250's LUT table, pass 275's gate runner.
    print("PARSE DEFECTS -- yosys cannot read the Verilog  : %d" % len(defects))
    print("absent $readmem data file (design is fine)      : %d" % len(missing_data))
    print("file halts itself at elaboration ($finish/$stop): %d" % len(halted))
    print("testbenches, any cause (not synthesis targets)  : %d" % len(tb_failed))
    print()
    if buckets:
        print("%6s  %s" % ("count", "class of parse defect"))
        for cls, names in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
            print("%6d  %s" % (len(names), cls))
            show = names if verbose else names[:3]
            for n in show:
                print("          %s" % n)
            if not verbose and len(names) > 3:
                print("          ... and %d more" % (len(names) - 3))
    else:
        print("every synthesis source parses.")
    for label, rows in (("absent data file", missing_data),
                        ("halts at elaboration", halted)):
        if rows:
            print()
            print("%s:" % label)
            for base, err in rows:
                print("    %-32s %s" % (base, err[:70]))
    # Only a parse defect fails this gate. A missing .mem is a data question and a
    # self-halting file is a testbench wearing the wrong name; neither says the
    # Verilog is wrong, and counting them here would make the exit code mean less
    # every time someone deleted a weights file.
    return 1 if defects else 0


if __name__ == "__main__":
    sys.exit(main())
