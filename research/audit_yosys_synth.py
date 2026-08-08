#!/usr/bin/env python3
"""Which of the synthesis sources actually SYNTHESISE?

Pass 245 asked whether yosys can READ each file and found 22 it cannot. Reading is
the front end. Synthesis is where unreachable logic, inferred latches, widths that
do not agree at elaboration, and missing submodules turn up -- and none of those
show up in a parse.

Each file is synthesised on its own with `synth_xilinx -flatten -nodsp`, with
`hierarchy -libdir` pointed at the same directory so a submodule instantiated by
name is found rather than left a black box. The top is the module whose name
matches the filename; failing that, the last module the file defines.

`-nodsp` is not optional. The repo's own note records DSP48E1 inference on the GF
multiplier turning into a routing failure.

Testbenches are excluded, on the same reasoning as pass 245: they are not
synthesis targets, and counting them would make the number mostly false.

This costs about 3.4 seconds a file, so the full tree is roughly half an hour at
six workers. Run it in the background and leave the worktree alone until it
finishes -- pass 239 killed its own job by removing the worktree underneath it.

Usage:  python3 research/audit_yosys_synth.py [--jobs N] [--limit N] [--verbose]
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
# The corona decode cells do not live here. Commit 32af5c242 -- "submodule: link
# tt-trinity-corona, remove 17 duplicate decode files" -- moved them into a
# submodule, and .github/workflows/ax7203-corona-decode.yml reads them from there:
#   SRC="fpga/openxc7-synth/corona_decode_posit8_ax7203.v \
#        external/tt-trinity-corona/src/rtl/posit8_decode.v"
# Without this path yosys reports "Module `\bf16_decode' ... is not part of the
# design" for about thirty wrappers that are perfectly buildable. The first run of
# this sweep did exactly that.
#
# AND: a git worktree does NOT carry submodule contents. Run inside one, this
# directory is empty even when the main tree has it populated -- which is how the
# first run produced a class of failures that do not exist.
CORONA = os.path.join(ROOT, "external", "tt-trinity-corona", "src", "rtl")

MODULE = re.compile(r"^\s*module\s+(\w+)", re.M)
ERR = re.compile(r"^(?:.*?:\d+:\s*)?ERROR:\s*(.*)$", re.M)
LUTS = re.compile(r"^\s+(\d+)\s+LUT[1-6]\s*$", re.M)
NUM = re.compile(r"\b\d+\b")
QUOTED = re.compile(r"[`'\"]([^`'\"]*)[`'\"]")


# *_mock.v files exist so that IVERILOG can elaborate a design that instantiates a
# Xilinx primitive. yosys ships its own cells_sim.v, so reading a mock alongside
# it is a re-definition, not a defect in the mock.
def is_mock(path):
    return os.path.basename(path).endswith("_mock.v")


def is_testbench(path):
    b = os.path.basename(path)
    return (b.endswith("_tb.v") or b.startswith("tb_") or "_testbench" in b
            or b.endswith("_test.v") or re.search(r"_tb\d*\.v$", b) is not None)


def classify(msg):
    m = QUOTED.sub("<name>", msg)
    m = NUM.sub("<n>", m)
    return m.strip()[:110]


def top_of(path, src):
    stem = os.path.basename(path)[:-2]
    mods = MODULE.findall(src)
    if not mods:
        return None
    return stem if stem in mods else mods[-1]


def run_one(path):
    src = open(path, encoding="utf-8", errors="replace").read()
    top = top_of(path, src)
    if top is None:
        return path, "no module defined", None
    libdirs = "-libdir %s" % SYNTH
    if os.path.isdir(CORONA) and glob.glob(os.path.join(CORONA, "*.v")):
        libdirs += " -libdir %s" % CORONA
    script = ("read_verilog %s; hierarchy -top %s %s; "
              "synth_xilinx -flatten -nodsp; stat" % (path, top, libdirs))
    r = subprocess.run(["yosys", "-p", script], capture_output=True, text=True,
                       timeout=600)
    out = r.stdout + r.stderr
    if r.returncode != 0:
        hits = ERR.findall(out)
        return path, (hits[0].strip() if hits else out.strip().splitlines()[-1][:120]), None
    got = LUTS.findall(out)
    half = len(got) // 2 or len(got)
    return path, None, (sum(int(x) for x in got[-half:]) if got else 0)


def main():
    verbose = "--verbose" in sys.argv
    jobs = 6
    if "--jobs" in sys.argv:
        jobs = int(sys.argv[sys.argv.index("--jobs") + 1])
    files = [f for f in sorted(glob.glob(os.path.join(SYNTH, "*.v")))
             if not is_testbench(f) and not is_mock(f)]
    if "--limit" in sys.argv:
        files = files[:int(sys.argv[sys.argv.index("--limit") + 1])]
    if not files:
        print("nothing to do")
        return 2

    if not (os.path.isdir(CORONA) and glob.glob(os.path.join(CORONA, "*.v"))):
        print("WARNING: %s has no Verilog." % CORONA)
        print("         If this is a git worktree, the submodule is not populated")
        print("         here and about thirty corona wrappers will report a missing")
        print("         module that is not actually missing. Run from the main tree.")
        print()
    ok, failed, luts = 0, [], 0
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = {ex.submit(run_one, f): f for f in files}
        for fut in concurrent.futures.as_completed(futs):
            done += 1
            try:
                path, err, n = fut.result()
            except subprocess.TimeoutExpired:
                failed.append((os.path.basename(futs[fut]), "timed out after 600s"))
                continue
            except Exception as e:                    # noqa: BLE001
                failed.append((os.path.basename(futs[fut]), "runner: %s" % type(e).__name__))
                continue
            if err:
                failed.append((os.path.basename(path), err))
            else:
                ok += 1
                luts += n or 0
            if done % 200 == 0:
                print("  ... %d/%d" % (done, len(files)), flush=True)

    buckets = collections.defaultdict(list)
    for base, err in failed:
        buckets[classify(err)].append(base)

    print()
    print("synthesis sources attempted : %d" % len(files))
    print("SYNTHESISED                 : %d" % ok)
    print("failed                      : %d" % len(failed))
    print("total LUTs across the ones that built : %d" % luts)
    print()
    if buckets:
        print("%6s  %s" % ("count", "class of failure"))
        for cls, names in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
            print("%6d  %s" % (len(names), cls))
            show = names if verbose else names[:3]
            for n in show:
                print("          %s" % n)
            if not verbose and len(names) > 3:
                print("          ... and %d more" % (len(names) - 3))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
