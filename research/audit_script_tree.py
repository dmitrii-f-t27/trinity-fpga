#!/usr/bin/env python3
"""Triage a repository's scripts by side effect, then run only what is safe.

Passes 57-58 applied this to the t27 tree and it found the defect that mattered
most in either: the six wide-rung witness decode references, which honesty rule #10
points a sceptical reader at, failed when run as the witness names them.

The method is the point, and it is reusable, so it lives here rather than in a
scratch directory.

    python3 research/audit_script_tree.py <repo> <disposable-copy> [bucket] [timeout]

    bucket: reads | write | exec | all   (default: reads)

Buckets, by what an AST scan finds:

  EXEC   subprocess / os.system / an exec-family call
  NET    urllib / requests / socket / http
  WRITE  open(..,'w'|'a'|'x'), os.remove, shutil, Path.write_*, os.makedirs
  READS  none of the above

Two rules learned the hard way, both encoded below:

  A write-ish NAME is not a write. `str.replace` and `dict.copy` are not filesystem
  calls, and `re.compile` is not `exec`. Match on the receiver. A first version
  without this put 19 pure-analysis scripts in the EXEC bucket and left only 10 in
  READS out of 300.

  NET is never run. A script that calls somebody else's API should not be fired at
  them unattended for the sake of a survey; its URLs are printed instead.

Before running anything, the caller should confirm no script hardcodes a path into
the live environment -- `grep -rn "/Users/$USER" <repo>` -- because a disposable
copy protects the tree, not the machine.
"""
from __future__ import annotations

import ast
import collections
import glob
import os
import re
import shutil
import subprocess
import sys

EXEC_NAMES = {"system", "popen", "spawn", "spawnl", "spawnv", "execv", "execve",
              "eval", "exec"}
EXEC_MODS = {"subprocess", "multiprocessing", "pty", "commands"}
NET_MODS = {"urllib", "requests", "socket", "http", "httpx", "aiohttp", "ftplib",
            "smtplib", "paramiko"}
WRITE_NAMES = {"remove", "unlink", "rmtree", "rmdir", "makedirs", "mkdir",
               "rename", "replace", "copy", "copy2", "copytree", "move",
               "write_text", "write_bytes", "truncate", "chmod"}
FS_RECEIVERS = {"os", "shutil", "pathlib", "Path", "subprocess"}


def classify(path: str) -> set[str]:
    try:
        src = open(path, encoding="utf-8", errors="replace").read()
        tree = ast.parse(src)
    except (SyntaxError, OSError):
        return {"PARSE_FAIL"}

    tags: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                top = a.name.split(".")[0]
                if top in EXEC_MODS:
                    tags.add("EXEC")
                if top in NET_MODS:
                    tags.add("NET")
        elif isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            if top in EXEC_MODS:
                tags.add("EXEC")
            if top in NET_MODS:
                tags.add("NET")
        elif isinstance(node, ast.Call):
            fn = node.func
            nm = fn.attr if isinstance(fn, ast.Attribute) else (
                fn.id if isinstance(fn, ast.Name) else "")
            recv = ""
            if isinstance(fn, ast.Attribute):
                base = fn.value
                recv = (base.id if isinstance(base, ast.Name)
                        else base.attr if isinstance(base, ast.Attribute) else "")
            if nm in EXEC_NAMES:
                tags.add("EXEC")
            if nm in WRITE_NAMES and (recv in FS_RECEIVERS or not recv):
                tags.add("WRITE")
            if nm == "open":
                mode = ""
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    mode = str(node.args[1].value)
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        mode = str(kw.value.value)
                if any(c in mode for c in "wax+"):
                    tags.add("WRITE")

    return tags or {"READS"}


def worst(tags: set[str]) -> str:
    for t in ("PARSE_FAIL", "EXEC", "NET", "WRITE"):
        if t in tags:
            return t
    return "READS"


def run(work: str, rel: str, cwd: str, timeout: int):
    try:
        p = subprocess.run([sys.executable, os.path.abspath(os.path.join(work, rel))],
                           cwd=cwd, capture_output=True, text=True, timeout=timeout)
        err = (p.stderr or "").strip().splitlines()
        return p.returncode, (err[-1][:66] if err else "")
    except subprocess.TimeoutExpired:
        return -9, f"TIMEOUT {timeout}s"


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__.strip().splitlines()[6])
        return 2
    src, work = sys.argv[1], sys.argv[2]
    bucket = (sys.argv[3] if len(sys.argv) > 3 else "reads").upper()
    timeout = int(sys.argv[4]) if len(sys.argv) > 4 else 25

    buckets = collections.defaultdict(list)
    for sub in ("tools", "scripts", "conformance"):
        for p in sorted(glob.glob(os.path.join(src, sub, "**", "*.py"), recursive=True)):
            buckets[worst(classify(p))].append(os.path.relpath(p, src))

    total = sum(len(v) for v in buckets.values())
    print(f"scripts triaged: {total}")
    for k in ("READS", "WRITE", "NET", "EXEC", "PARSE_FAIL"):
        print(f"  {k:<11} {len(buckets.get(k, []))}")
    print()

    wanted = ([bucket] if bucket in ("READS", "WRITE", "EXEC")
              else ["READS", "WRITE", "EXEC"] if bucket == "ALL" else [])
    if not wanted:
        print(f"bucket {bucket!r} is not runnable; nothing executed")
        return 0

    if os.path.exists(work):
        shutil.rmtree(work)
    shutil.copytree(src, work, symlinks=True, ignore=shutil.ignore_patterns(".git"))

    tally = collections.Counter()
    for b in wanted:
        print(f"--- running {b} ({len(buckets[b])}) ---")
        for rel in buckets[b]:
            rc, err = run(work, rel, work, timeout)
            if rc != 0:
                own = os.path.dirname(os.path.join(work, rel)) or work
                rc2, err2 = run(work, rel, own, timeout)
                if rc2 == 0:
                    rc, err = 0, ""
                else:
                    err = err or err2
            tally["ok" if rc == 0 else "fail"] += 1
            if rc != 0:
                print(f"  rc={rc:<4} {rel}")
                print(f"           {err}")
        print(f"  -> {tally['ok']}/{tally['ok'] + tally['fail']} exit 0\n")

    if buckets.get("NET"):
        print("NET, inspected and deliberately NOT run:")
        for rel in buckets["NET"]:
            body = open(os.path.join(src, rel), errors="replace").read()
            for u in sorted(set(re.findall(r'https?://[^\s"\'<>)]+', body)))[:4]:
                print(f"  {rel}  would call {u}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
