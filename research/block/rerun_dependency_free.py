#!/usr/bin/env python3
"""Re-run every script here that needs neither weights nor a foreign path, and
compare what it writes against the record committed beside it.

    python3 rerun_dependency_free.py              # ~20 minutes, writes RERUN.json
    python3 rerun_dependency_free.py --list       # just say which scripts qualify
    python3 rerun_dependency_free.py --timeout 60

**It never writes into this directory.** Everything runs in a throwaway copy
under the system temp dir, because a self-test that mutates the tree it is
testing has, in this codebase's history, truncated a shipped file to zero bytes.
The originals are the comparison set, so they must stay untouched.

Differences are classified per JSON leaf, not per file. A record whose numbers
all reproduce and which differs only in its `provenance` block is a different
event from one whose numbers moved, and collapsing the two would hide the more
interesting of them.
"""
import argparse
import ast
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(HERE, "RERUN.json")
HEAVY = {"torch", "transformers", "datasets", "accelerate", "safetensors",
         "sentencepiece", "tokenizers", "bitsandbytes", "pyarrow"}
FOREIGN = re.compile(r"/private/tmp|/Users/(?!playra\b)[A-Za-z0-9_.-]+/|/home/[A-Za-z0-9_.-]+/")
sys.path.insert(0, HERE)
from reproduce_index import PACKAGE as SELF  # noqa: E402  -- one home for that list


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def qualifies(path):
    src = open(path, encoding="utf-8", errors="replace").read()
    if FOREIGN.search(src):
        return False
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    return not (mods & HEAVY)


def leaves(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from leaves(v, p + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from leaves(v, p + "/%d" % i)
    else:
        yield p, o


def compare(a_path, b_path):
    """Leaf-level diff of two records, split into provenance and substance."""
    try:
        A, B = dict(leaves(json.load(open(a_path)))), dict(leaves(json.load(open(b_path))))
    except Exception:                                # noqa: BLE001
        return {"comparable": False}
    keys = set(A) | set(B)
    diff = [k for k in keys if A.get(k, "\0a") != B.get(k, "\0b")]
    prov = [k for k in diff if k.startswith("/provenance")]
    return {"comparable": True, "leaves": len(keys), "differing": len(diff),
            "provenance_only": len(diff) == len(prov),
            "substantive": sorted(set(diff) - set(prov))[:12]}


#: A failure says something different depending on why it failed, and the three
#: kinds are not interchangeable: an absent input is a gap in the repository, a
#: timeout is a budget, and anything else is a defect in the script.
MISSING = re.compile(r"FileNotFoundError|No such file|missing |not present|no checkpoints")
NAMED = re.compile(r"[A-Za-z0-9_./\-]+\.(?:json|npy|npz|csv|txt|pt|safetensors)")


def scrub(msg, sandbox):
    """Rewrite the sandbox root out of an error message, as `./`.

    Both spellings, because they are not interchangeable on macOS: `mkdtemp`
    hands back `/var/folders/...` and the kernel reports the same file through
    `/private/var/folders/...`. Matching only the one we were given left a
    `/private.` stump in the text and, worse, made the `sandbox_gap` test below
    silently unreachable -- a classifier that can only ever return one answer.
    """
    for root in sorted({sandbox, os.path.realpath(sandbox)}, key=len, reverse=True):
        msg = msg.replace(root + os.sep, "./").replace(root, ".")
    return msg


def reason_for(entry):
    if entry["rc"] == 0:
        return ""
    if entry["rc"] == -9:
        return "timeout"
    err = entry["error"] or ""
    if MISSING.search(err):
        # A missing input is a gap in the repository only if the file really is
        # absent from it. If the source tree holds it, the sandbox failed to copy
        # it and the finding is about this harness, not about the research.
        # Paths here have already had the sandbox root rewritten to `./`.
        for hit in NAMED.findall(err):
            if hit.startswith("./") and os.path.exists(os.path.join(HERE, hit[2:])):
                return "sandbox_gap"
        return "missing_input"
    return "script_error"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--timeout", type=int, default=180)
    a = ap.parse_args()

    sources = [p for p in glob.glob(os.path.join(HERE, "*.py"))
               if os.path.basename(p) not in SELF]
    pure = sorted(os.path.basename(p) for p in sources if qualifies(p))
    print("%d of %d scripts need neither weights nor a foreign path"
          % (len(pure), len(sources)))
    if a.list:
        for s in pure:
            print("  " + s)
        return

    sandbox = tempfile.mkdtemp(prefix="blockrerun-")
    orig = os.path.join(sandbox, ".orig")
    os.makedirs(orig)
    for f in glob.glob(os.path.join(HERE, "*")):
        if os.path.isfile(f):
            shutil.copy2(f, sandbox)
            if f.endswith(".json"):
                shutil.copy2(f, orig)
        elif os.path.isdir(f) and os.path.basename(f) != "__pycache__":
            # Subdirectories are inputs too. Copying only files once made a
            # script's own missing data look like a missing directory.
            shutil.copytree(f, os.path.join(sandbox, os.path.basename(f)))
    print("sandbox:", sandbox, "\n")

    def state():
        """basename -> (mtime_ns, sha256) for every record in the sandbox."""
        return {os.path.basename(f): (os.stat(f).st_mtime_ns, sha256(f))
                for f in glob.glob(os.path.join(sandbox, "*.json"))}

    report = []
    for name in pure:
        before = state()
        t = time.time()
        try:
            r = subprocess.run([sys.executable, name], cwd=sandbox,
                               capture_output=True, text=True, timeout=a.timeout)
            rc = r.returncode
            err = (r.stderr or "").strip().splitlines()[-1:]
        except subprocess.TimeoutExpired:
            rc, err = -9, ["timeout %ds" % a.timeout]
        dt = time.time() - t
        after = state()
        # A rewrite that lands byte-identical changes no hash, so comparing
        # hashes counts it as nothing happening: the reproduction that worked
        # becomes invisible and only the failures are seen. mtime sees the write.
        written = sorted(k for k in after if before.get(k) != after[k])

        # The sandbox path is a temp directory on whoever ran this. Recording it
        # verbatim would put a machine-local path into a committed report whose
        # own finding is that machine-local paths do not survive the machine.
        msg = scrub(err[0][:400], sandbox) if err and rc != 0 else ""
        entry = {"script": name, "rc": rc, "seconds": round(dt, 1),
                 "error": msg[:200],
                 "identical": [], "differed": {}, "new": []}
        for k in written:
            op = os.path.join(orig, k)
            if not os.path.exists(op):
                entry["new"].append(k)
            elif sha256(op) == after[k][1]:
                entry["identical"].append(k)
            else:
                entry["differed"][k] = compare(op, os.path.join(sandbox, k))
        report.append(entry)
        prov_only = sum(1 for v in entry["differed"].values() if v.get("provenance_only"))
        print("%-34s rc=%-3s %6.1fs  identical=%d differed=%d (%d provenance-only) new=%d %s"
              % (name, rc, dt, len(entry["identical"]), len(entry["differed"]),
                 prov_only, len(entry["new"]), entry["error"][:60]), flush=True)

    for e in report:
        e["reason"] = reason_for(e)

    summary = {
        "generated_by": "rerun_dependency_free.py",
        "python": sys.version.split()[0],
        "timeout_seconds": a.timeout,
        "scripts_run": len(report),
        "exit_zero": sum(1 for r in report if r["rc"] == 0),
        "failed_by_reason": {k: sum(1 for r in report if r["reason"] == k)
                             for k in sorted({r["reason"] for r in report if r["reason"]})},
        "records_identical": sum(len(r["identical"]) for r in report),
        "records_differed": sum(len(r["differed"]) for r in report),
        "differed_provenance_only": sum(
            1 for r in report for v in r["differed"].values() if v.get("provenance_only")),
        "records_new": sum(len(r["new"]) for r in report),
        "scripts": report,
    }
    json.dump(summary, open(REPORT, "w", encoding="utf-8"), indent=2, sort_keys=True)
    shutil.rmtree(sandbox, ignore_errors=True)
    print("\n%(scripts_run)d run | %(exit_zero)d exited 0 | %(records_identical)d records "
          "byte-identical | %(records_differed)d differed, of which "
          "%(differed_provenance_only)d in provenance only" % summary)
    if summary["failed_by_reason"]:
        print("failures: " + " | ".join("%s %d" % (k, v) for k, v
                                        in summary["failed_by_reason"].items()))
    print("wrote", os.path.basename(REPORT))


if __name__ == "__main__":
    main()
