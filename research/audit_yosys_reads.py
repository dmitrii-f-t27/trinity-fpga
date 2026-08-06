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

Usage:  python3 research/audit_yosys_reads.py [--verbose] [--jobs N]

Exits non-zero if any file yosys cannot read.
"""
import collections
import concurrent.futures
import glob
import os
import re
import subprocess
import sys

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

    failed, tb_failed = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        for path, err in ex.map(read_one, files):
            if err:
                (tb_failed if is_testbench(path) else failed).append(
                    (os.path.basename(path), err))

    buckets = collections.defaultdict(list)
    for base, err in failed:
        buckets[classify(err)].append(base)

    tbs = sum(1 for f in files if is_testbench(f))
    print("files under fpga/openxc7-synth : %d  (%d of them testbenches)"
          % (len(files), tbs))
    print("SYNTHESIS SOURCES yosys cannot read : %d" % len(failed))
    print("testbenches it cannot read          : %d  (not a defect -- reported for completeness)"
          % len(tb_failed))
    print()
    if buckets:
        print("%6s  %s" % ("count", "class of error"))
        for cls, names in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
            print("%6d  %s" % (len(names), cls))
            show = names if verbose else names[:3]
            for n in show:
                print("          %s" % n)
            if not verbose and len(names) > 3:
                print("          ... and %d more" % (len(names) - 3))
    else:
        print("every file reads.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
