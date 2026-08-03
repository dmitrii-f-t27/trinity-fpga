#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Are the external witnesses still the files the claims were made against?

Pass 194 retracted a witness that turned out to be the thing it witnessed. This is the
other half of the same question, asked of the witnesses that *are* real.

The strongest external results in this campaign -- posit8 exhaustively against SoftPosit,
takum against libtakum -- do not compare against a library. They compare against **dumps**:
tab-separated files of (code, value) produced once by those libraries and read back by
`research/crossval_softposit.py` and `research/crossval_libtakum.py`. That is a sound
design; a dump is reproducible and a library version is not always installable.

It was undermined by where the dumps lived. All of them sat in a session scratch
directory, with no hash recorded anywhere, no size, no note of which library or version
produced them, and no copy in the repository. The comparisons were real and the evidence
was one `rm` from gone -- and a file with the right *name* and wrong *contents* would have
been read without complaint.

So:

  * `conformance/witness/` now holds every dump small enough for the repository's own
    1 MB rule -- spx8, spx32, lt8, ltlog8, ltlog8_hex. Those cover the exhaustive cases,
    which are the strongest claims: posit8 over all 256 codes, takum8 over all 256.
  * `conformance/witness/MANIFEST.json` records the SHA-256, byte count, witness and
    consumer of all eleven, including the six too large to commit.
  * This file checks a dump against the manifest before anyone compares against it.

Hashes in the manifest were produced by `shasum -a 256` and injected mechanically. None
was typed by hand, which is the standing rule in this repository and exists because a
transcribed hash is a hash nobody can check.

    python3 research/audit_witness_artefacts.py [--dir D] [--verbose] [--self-check]

Exit 0 when every artefact present matches the manifest, 1 on a mismatch, 2 when nothing
could be checked -- which is a skip, never a pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WITNESS = os.path.join(ROOT, "conformance", "witness")
MANIFEST = os.path.join(WITNESS, "MANIFEST.json")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest():
    if not os.path.exists(MANIFEST):
        return None
    return json.load(open(MANIFEST, encoding="utf-8"))


def search_dirs(explicit=None):
    """Where a dump might be, most authoritative first."""
    out = []
    if explicit:
        out.append(explicit)
    out.append(WITNESS)
    env = os.environ.get("TRINITY_ARTEFACTS")
    if env:
        out.append(env)
    out.append(os.path.join(ROOT, "artefacts"))
    return [d for d in out if d and os.path.isdir(d)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        return self_check()

    man = load_manifest()
    if man is None:
        print(f"no manifest at {MANIFEST}")
        print("SKIPPED -- not a pass.")
        return 2

    dirs = search_dirs(args.dir)
    found = mismatch = absent = 0
    rows = []
    for a in man["artefacts"]:
        path = None
        for d in dirs:
            p = os.path.join(d, a["name"])
            if os.path.exists(p):
                path = p
                break
        if path is None:
            absent += 1
            rows.append((a["name"], "absent", a["in_repo"] is not None, None))
            continue
        got = sha256(path)
        ok = got == a["sha256"]
        found += 1
        mismatch += not ok
        rows.append((a["name"], "ok" if ok else "MISMATCH",
                     a["in_repo"] is not None, path))

    print(f"artefacts in the manifest            : {len(man['artefacts'])}")
    print(f"  present and matching               : {found - mismatch}")
    print(f"  present and DIFFERENT              : {mismatch}")
    print(f"  absent                             : {absent}\n")
    for name, state, in_repo, path in rows:
        tag = "repo" if in_repo else "ext "
        note = "" if state != "absent" else \
               ("  (committed copy missing!)" if in_repo else
                "  (too large to commit; regenerate to use)")
        print(f"  [{tag}] {name:<18} {state}{note}")
        if args.verbose and path:
            print(f"          {path}")

    print("""
An artefact that is absent is not a failure here -- six of the eleven are past the
repository's 1 MB rule and are expected to be regenerated. An artefact that is PRESENT and
different is: it means a comparison ran, or will run, against something other than the file
the published numbers came from, and nothing else in the corpus would notice.

The five committed dumps are the exhaustive cases on purpose. posit8 over all 256 codes and
takum8 over all 256 are the strongest claims the campaign makes from an external witness,
and they are the ones that must survive this session ending.""")
    if mismatch:
        return 1
    if not found:
        print("\nNothing was checked. SKIPPED -- not a pass.")
        return 2
    return 0


def self_check() -> int:
    """A manifest that cannot catch a substituted file is decoration.

    Corrupt a committed dump by one byte in a temporary copy, and require the hash check
    to reject it; then confirm the untouched original passes.
    """
    man = load_manifest()
    if man is None:
        print("no manifest; nothing to control")
        return 1
    entry = next((a for a in man["artefacts"] if a["in_repo"]), None)
    if entry is None:
        print("no committed artefact to test with")
        return 1
    path = os.path.join(ROOT, entry["in_repo"])
    clean = sha256(path) == entry["sha256"]
    print(f"  {entry['name']}: committed copy matches the manifest -> {clean}")

    data = bytearray(open(path, "rb").read())
    data[len(data) // 2] ^= 1
    tmp = path + ".selfcheck"
    try:
        open(tmp, "wb").write(bytes(data))
        caught = sha256(tmp) != entry["sha256"]
    finally:
        os.remove(tmp)
    print(f"  one bit flipped in a copy -> rejected: {caught}")
    print(f"  original untouched -> {sha256(path) == entry['sha256']}")

    ok = clean and caught
    print(f"\nself-check: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
