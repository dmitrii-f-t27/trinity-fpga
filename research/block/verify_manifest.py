#!/usr/bin/env python3
"""Check this directory against MANIFEST.json. Standard library only.

    python3 verify_manifest.py            # every record and source
    python3 verify_manifest.py --records  # records only

Exit status is 0 when every file listed is present and hashes to what the
manifest says, and 1 otherwise. Files present here but absent from the manifest
are reported as `extra` and do not fail the run, because a working tree may
legitimately hold scratch output.

This file deliberately recomputes nothing but sha256: the manifest is the claim,
this is the test of it. Regenerate the claim with `reproduce_index.py`.
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "MANIFEST.json")
sys.path.insert(0, HERE)
from reproduce_index import PACKAGE  # noqa: E402  -- one home for that list


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def check(section, entries, suffix):
    missing, wrong, ok = [], [], 0
    for name, meta in sorted(entries.items()):
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            missing.append(name)
            continue
        if sha256(path) != meta["sha256"]:
            wrong.append(name)
            continue
        ok += 1
    present = {f for f in os.listdir(HERE) if f.endswith(suffix)}
    extra = sorted(present - set(entries) - set(PACKAGE))
    print("%-8s %4d listed | %4d match | %d missing | %d differ | %d extra"
          % (section, len(entries), ok, len(missing), len(wrong), len(extra)))
    for label, items in (("missing", missing), ("differs", wrong), ("extra", extra)):
        for n in items[:20]:
            print("   %-8s %s" % (label, n))
        if len(items) > 20:
            print("   %-8s ... and %d more" % (label, len(items) - 20))
    return not (missing or wrong)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--records", action="store_true", help="skip the Python sources")
    a = ap.parse_args()

    if not os.path.exists(MANIFEST):
        sys.exit("no MANIFEST.json here -- run: python3 reproduce_index.py")
    m = json.load(open(MANIFEST, encoding="utf-8"))

    good = check("records", m["records"], ".json")
    if not a.records:
        good = check("sources", m["scripts"], ".py") and good

    rec = m["records"].values()
    pinned = sum(1 for r in rec if r["identity_fields"])
    named = [r["provenance"]["harness"] for r in rec if r.get("provenance")]
    agrees = sum(1 for r in rec if r.get("checkpoint_revision_is_hub_main_today"))
    print("\n%d of %d records name a checkpoint; %d of those name a revision the Hub "
          "still\nresolves to. %d records name a harness and %d of them hash-match the "
          "file in\nthis tree. Everything else -- and what it is worth -- is in "
          "REPRODUCE.md."
          % (pinned, len(m["records"]), agrees,
             len(named), sum(1 for h in named if h.get("matches_tree"))))
    sys.exit(0 if good else 1)


if __name__ == "__main__":
    main()
