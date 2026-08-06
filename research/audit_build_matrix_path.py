#!/usr/bin/env python3
"""Synthesise the compute targets the way build-matrix.yml actually does.

Pass 268 established that the 3,203 corona_compute_* wrappers are live build
targets of .github/workflows/build-matrix.yml. That workflow does NOT do what
research/audit_yosys_synth.py did. It reads exactly three files --

    READS="gf_adder_param.v gf_mul_param.v ${DESIGN}.v"

-- with no -libdir, from inside fpga/openxc7-synth, and it picks flags by
operation:

    mul   -> -flatten -abc9 -nocarry -nodsp -arch xc7
    other -> -flatten -abc9 -nocarry -arch xc7

Those are different conditions, and the difference is not cosmetic: without
-libdir a wrapper that instantiates anything beyond those two cores fails, and
without -nodsp a multiplier-shaped datapath can infer DSP48E1 blocks that
Project X-Ray only partially documents. Two wrappers already showed the gap in
pass 268.

This runs that exact recipe over every compute target and reports what a dispatch
would do.

Usage:  python3 audit_build_matrix_path.py [--jobs N] [--limit N] [--verbose]
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
WF = os.path.join(ROOT, ".github", "workflows", "build-matrix.yml")
READS_LINE = re.compile(r'READS="([^"]*)\$\{DESIGN\}\.v"')


def workflow_cores():
    """Read the core list out of the workflow rather than hard-coding it.

    The point of this audit is to test what a dispatch would do, so the source
    list has to come from the workflow. Hard-coding it means the audit passes
    while the workflow fails, which is the failure mode this whole series keeps
    running into.
    """
    try:
        m = READS_LINE.search(open(WF, encoding="utf-8").read())
    except OSError:
        return "gf_adder_param.v gf_mul_param.v"
    return m.group(1).strip() if m else "gf_adder_param.v gf_mul_param.v"


CORES = workflow_cores()
NUM = re.compile(r"\b\d+\b")
QUOTED = re.compile(r"[`'\"]([^`'\"]*)[`'\"]")
NAME = re.compile(r"^corona_compute_(?P<fmt>.+?)_(?P<op>[a-z0-9_]+)_ax7203\.v$")


def classify(msg):
    return NUM.sub("<n>", QUOTED.sub("<name>", msg)).strip()[:110]


def run_one(path):
    base = os.path.basename(path)
    m = NAME.search(base)
    if not m:
        return base, "not a compute target"
    op = m.group("op")
    flags = ("-flatten -abc9 -nocarry -nodsp -arch xc7" if op == "mul"
             else "-flatten -abc9 -nocarry -arch xc7")
    script = "read_verilog %s %s; synth_xilinx %s" % (CORES, base, flags)
    try:
        r = subprocess.run(["yosys", "-p", script], cwd=SYNTH,
                           capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return base, "timed out after 300s"
    if r.returncode == 0:
        return base, None
    out = r.stdout + r.stderr
    hits = ERR.findall(out)
    return base, (hits[0].strip() if hits else out.strip().splitlines()[-1][:120])


def main():
    verbose = "--verbose" in sys.argv
    jobs = 6
    if "--jobs" in sys.argv:
        jobs = int(sys.argv[sys.argv.index("--jobs") + 1])
    files = sorted(glob.glob(os.path.join(SYNTH, "corona_compute_*_ax7203.v")))
    if "--limit" in sys.argv:
        files = files[:int(sys.argv[sys.argv.index("--limit") + 1])]
    ok, failed, done = 0, [], 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        for base, err in ex.map(run_one, files):
            done += 1
            if err:
                failed.append((base, err))
            else:
                ok += 1
            if done % 200 == 0:
                print("  ... %d/%d" % (done, len(files)), flush=True)

    buckets = collections.defaultdict(list)
    for base, err in failed:
        buckets[classify(err)].append(base)

    print()
    print("cores from build-matrix.yml : %s" % CORES)
    print("compute targets attempted : %d" % len(files))
    print("would BUILD on dispatch   : %d" % ok)
    print("would FAIL                : %d" % len(failed))
    print()
    if buckets:
        print("%6s  %s" % ("count", "class"))
        for cls, names in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
            print("%6d  %s" % (len(names), cls))
            for n in (names if verbose else names[:3]):
                print("          %s" % n)
            if not verbose and len(names) > 3:
                print("          ... and %d more" % (len(names) - 3))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
