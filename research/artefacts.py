#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Where the large artefacts live, and what to do when they do not.

Six checks in this campaign hardcoded a path containing a session identifier:

    /private/tmp/claude-501/-Users-playom-trinity-fpga/<uuid>/scratchpad

That directory belongs to one session on one machine. It will not exist for a reader,
and it will not exist for the next session either. Six results rested on it, and pass
169 found this by running the whole suite in a clean tree and asking which checks still
believed they had their inputs.

Nothing here is downloaded automatically. These artefacts are large, come from outside
this repository, and fetching them silently is how a check ends up reporting a result
nobody can trace. Instead, resolution is explicit and the failure message says exactly
what to fetch and how.

Resolution order:

    1. the path passed on the command line, if the caller takes one
    2. $TRINITY_ARTEFACTS
    3. ./artefacts/ beside the repository root
    4. the legacy scratchpad, if it happens to exist -- so an in-flight session keeps
       working while the convention moves

A check that cannot find its input must exit 2 and print the command that produces it.
Exiting 0 on a missing input is the failure this whole set exists to prevent: a clean
run and an empty run look identical from outside.
"""
from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LEGACY = ("/private/tmp/claude-501/-Users-playom-trinity-fpga/"
          "3a885a60-490c-4733-abfd-86bfa298080d/scratchpad")

# How to produce each artefact, printed when it is missing.
RECIPES = {
    "takum8.json":
        "gh api repos/gHashTag/t27/contents/conformance/vectors/"
        "takum8_conformance_v0.json --jq .content | base64 -d > takum8.json",
    "takum16.json":
        "gh api repos/gHashTag/t27/contents/conformance/vectors/"
        "takum16_conformance_v0.json --jq .content | base64 -d > takum16.json",
    "posit8.json":
        "gh api repos/gHashTag/t27/contents/conformance/vectors/"
        "posit8_conformance_v0.json --jq .content | base64 -d > posit8.json",
    "spx8.tsv":
        "build SoftPosit, then dump convertPX2ToDouble over all 256 codes "
        "left-aligned in a 32-bit container -- see research/crossval_softposit.py",
    "ltlog8.tsv":
        "build libtakum, then dump takum_log8_to_float64 over all 256 codes -- "
        "see research/libtakum_bridge.c",
    "rtl_p8.txt":
        "iverilog -g2012 -o /tmp/tb fpga/openxc7-synth/tb_posit8_es2_decode.v "
        "fpga/openxc7-synth/posit8_es2_decode.v fpga/openxc7-synth/posit16_decode.v "
        "&& /tmp/tb > rtl_p8.txt",
}


def artefact_dir(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("TRINITY_ARTEFACTS")
    if env:
        return env
    local = os.path.join(ROOT, "artefacts")
    if os.path.isdir(local):
        return local
    if os.path.isdir(LEGACY):
        return LEGACY
    return local                       # report against the documented location


def require(name: str, explicit_dir: str | None = None) -> str | None:
    """Absolute path to `name`, or None after explaining how to produce it."""
    path = os.path.join(artefact_dir(explicit_dir), name)
    if os.path.exists(path):
        return path
    print(f"missing artefact: {name}")
    print(f"  looked in       : {artefact_dir(explicit_dir)}")
    print(f"  override with   : --artefacts DIR, or $TRINITY_ARTEFACTS")
    if name in RECIPES:
        print(f"  produce it with : {RECIPES[name]}")
    print("\nNothing is assumed in its absence. Exit 2 means the check could not run,")
    print("which is not the same as running and finding nothing.")
    return None


if __name__ == "__main__":
    print(f"artefact directory: {artefact_dir()}")
    print(f"  exists          : {os.path.isdir(artefact_dir())}")
    for n in sorted(RECIPES):
        p = os.path.join(artefact_dir(), n)
        print(f"  {'present' if os.path.exists(p) else 'MISSING'}  {n}")
