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
import signal
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
    # Popen with a process GROUP, not subprocess.run.
    #
    # subprocess.run(timeout=...) kills only the DIRECT child on timeout and then
    # calls communicate() a second time with NO timeout to drain the pipes. yosys
    # spawns yosys-abc, which inherits those pipes; when yosys is killed but abc
    # survives, that second communicate() blocks forever. The signature is a live
    # parent with zero yosys children and no output -- which is exactly how this
    # sweep sat for three hours looking like slow progress.
    #
    # Killing the whole group reaps abc too, so the pipes close and the drain
    # returns.
    proc = subprocess.Popen(["yosys", "-p", script], cwd=SYNTH,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    try:
        so, se = proc.communicate(timeout=300)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        try:
            so, se = proc.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            return base, "timed out after 300s, and its pipes did not drain"
        return base, "timed out after 300s"
    if proc.returncode == 0:
        return base, None
    out = so + se
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
    stall = 900
    if "--stall" in sys.argv:
        stall = int(sys.argv[sys.argv.index("--stall") + 1])
    stalled = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        pending = set(ex.submit(run_one, f) for f in files)
        while pending:
            # wait() with a timeout, so a wedge is DETECTED rather than waited on.
            # ex.map yields in submission order and offers no way to tell "nothing
            # has finished for hours" from "the next one is slow".
            batch = concurrent.futures.wait(
                pending, timeout=stall,
                return_when=concurrent.futures.FIRST_COMPLETED)
            if not batch.done:
                stalled = True
                print("\nSTALLED: no target completed in %ds, %d outstanding."
                      % (stall, len(pending)), flush=True)
                print("Reporting %d results and stopping, rather than waiting "
                      "silently." % done, flush=True)
                for f in pending:
                    f.cancel()
                break
            for f in batch.done:
                pending.discard(f)
                base, err = f.result()
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
    # "attempted 3, would fail 0" after a stall reads as good news and is not.
    # Report what was actually MEASURED, and say plainly when the rest was not.
    print("compute targets in the tree : %d" % len(files))
    print("targets measured            : %d" % done)
    print("would BUILD on dispatch     : %d" % ok)
    print("would FAIL                  : %d" % len(failed))
    if done < len(files):
        print()
        print("NOT MEASURED                : %d  <- %s"
              % (len(files) - done,
                 "the run stalled and stopped" if stalled else "run was limited"))
        print("Those targets have not been shown to build. An unmeasured target is")
        print("not a passing one, and the counts above describe only the %d measured."
              % done)
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
