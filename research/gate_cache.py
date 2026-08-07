#!/usr/bin/env python3
"""A content-addressed cache for gates that re-derive the same answer every pass.

Two of the 65 gates in research/ time out under research/run_all_gates.py's 400s
budget: audit_yosys_reads.py, which asks yosys to parse all 3,594 Verilog files,
and audit_selftest_sensitivity.py, which mutates sixteen oracles five ways each
and runs a self-test per mutation. Both are worth having. Neither gets run,
because a gate nobody waits for is a gate nobody runs -- which is how pass 250's
LUT parser survived a pass, and how three gfternary packs went stale for two.

Almost all of that work is repeated. A Verilog file that yosys read last pass and
that has not changed since will read again. So cache the verdict against a key
that covers every input, and re-derive only what moved.

THE ONLY THING THAT MATTERS HERE IS THE KEY
-------------------------------------------
A cache whose key misses an input reports a stale verdict as a fresh one. That is
strictly worse than a slow gate: the slow gate is skipped and known to be
skipped, while the wrong-key cache is a green light that has stopped meaning
anything. Everything below is in service of the key.

    audit_yosys_reads     unit = one .v file. `read_verilog <file>` opens exactly
                          that file -- no include path, no libdir -- so the file's
                          own bytes plus the yosys version are the whole input.

    audit_selftest_       unit = one oracle. Its self-test imports other modules
    sensitivity           in conformance/, so the oracle's own bytes are NOT the
                          whole input. The key covers the transitive closure of
                          its conformance-local imports, computed by importing the
                          module in a subprocess and asking sys.modules which files
                          were loaded -- not by matching `import` lines with a
                          regex, which misses conditional and deferred imports and
                          would produce exactly the stale-green this comment is
                          about.

If you cannot state what the whole input is, do not add a cache here.

Both callers accept --no-cache, which bypasses this entirely and is what proves
the cache honest: the two must agree. research/audit_cache_honesty.py runs that
comparison.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, ".gate_cache")


def sha_files(paths):
    """One digest over an ordered set of files. Missing files are recorded as such
    rather than skipped -- a deleted dependency is a change."""
    h = hashlib.sha256()
    for p in sorted(set(paths)):
        h.update(os.path.basename(p).encode() + b"\0")
        try:
            with open(p, "rb") as fh:
                h.update(hashlib.sha256(fh.read()).digest())
        except OSError:
            h.update(b"<absent>")
    return h.hexdigest()


def tool_version(argv):
    """The tool is an input too. A yosys upgrade can change what parses."""
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        return (r.stdout or r.stderr).strip().splitlines()[0][:80]
    except Exception:
        return "<unknown>"


def python_imports_under(module_path, root):
    """Every file under `root` that importing `module_path` actually loads.

    Asked of Python rather than inferred from the source, because the question is
    what gets executed, and only the interpreter knows that.

    Returns the module itself plus its closure, or None if it will not import --
    in which case the caller must not cache, since it cannot know the inputs.
    """
    probe = (
        "import importlib.util,os,sys,json\n"
        "p=sys.argv[1]; root=os.path.realpath(sys.argv[2])\n"
        "sys.path.insert(0, os.path.dirname(p))\n"
        "s=importlib.util.spec_from_file_location('_probe', p)\n"
        "m=importlib.util.module_from_spec(s)\n"
        "s.loader.exec_module(m)\n"
        "out=[p]\n"
        "for mod in list(sys.modules.values()):\n"
        "    f=getattr(mod,'__file__',None)\n"
        "    if f and os.path.realpath(f).startswith(root+os.sep): out.append(f)\n"
        "print(json.dumps(sorted(set(out))))\n"
    )
    try:
        r = subprocess.run([sys.executable, "-c", probe, module_path, root],
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return None
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return None


class Cache:
    """unit -> (key, value). A unit whose key differs is re-derived."""

    def __init__(self, name, enabled=True):
        self.path = os.path.join(DIR, "%s.json" % name)
        self.enabled = enabled
        self.data = {}
        self.hits = 0
        self.misses = 0
        if enabled and os.path.exists(self.path):
            try:
                self.data = json.load(io.open(self.path, encoding="utf-8"))
            except Exception:
                self.data = {}          # a corrupt cache is a cold cache, never an error

    def get(self, unit, key):
        if not self.enabled or key is None:
            self.misses += 1
            return None
        got = self.data.get(unit)
        if got and got.get("key") == key:
            self.hits += 1
            return got
        self.misses += 1
        return None

    def put(self, unit, key, value):
        if not self.enabled or key is None:
            return
        self.data[unit] = {"key": key, "value": value}

    def save(self):
        if not self.enabled:
            return
        os.makedirs(DIR, exist_ok=True)
        tmp = self.path + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=1, sort_keys=True)
        os.replace(tmp, self.path)      # atomic: an interrupted run leaves the old cache

    def summary(self):
        total = self.hits + self.misses
        if not self.enabled:
            return "cache off"
        return "cache: %d reused, %d recomputed of %d" % (self.hits, self.misses, total)


if __name__ == "__main__":
    # SELF-TEST
    import tempfile
    fails = []
    with tempfile.TemporaryDirectory() as d:
        a = os.path.join(d, "a.txt")
        io.open(a, "w").write("one")
        k1 = sha_files([a])
        if sha_files([a]) != k1:
            fails.append("digest is not stable across calls")
        io.open(a, "w").write("two")
        if sha_files([a]) == k1:
            fails.append("digest did not move when the file did")
        if sha_files([a, os.path.join(d, "gone.txt")]) == sha_files([a]):
            fails.append("an absent dependency did not change the digest")

        # A cache miss on a changed key is the property the whole file exists for.
        c = Cache("_selftest", enabled=True)
        c.path = os.path.join(d, "c.json")
        c.put("u", "k1", {"err": None})
        if (c.get("u", "k1") or {}).get("value") != {"err": None}:
            fails.append("a matching key did not hit")
        if c.get("u", "k2") is not None:
            fails.append("a CHANGED KEY HIT -- the cache would report a stale verdict")
        c.save()
        if not os.path.exists(c.path):
            fails.append("save() wrote nothing")

        # The import probe must find a dependency, not just the module itself.
        dep = os.path.join(d, "dep.py")
        mod = os.path.join(d, "mod.py")
        io.open(dep, "w").write("X = 1\n")
        io.open(mod, "w").write("import dep\nY = dep.X\n")
        got = python_imports_under(mod, d)
        if not got or dep not in got:
            fails.append("the import probe missed a dependency: %r" % (got,))
        io.open(os.path.join(d, "bad.py"), "w").write("raise SystemError('no')\n")
        if python_imports_under(os.path.join(d, "bad.py"), d) is not None:
            fails.append("a module that will not import must return None, not a key")

    print("SELF-TEST gate_cache: %s" % ("FAIL" if fails else "6/6 pass"))
    for f in fails:
        print("  %s" % f)
    sys.exit(1 if fails else 0)
