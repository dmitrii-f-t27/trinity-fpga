#!/usr/bin/env python3
"""Structural FSM audit: verifies every decode/compute wrapper's frame FSM is
correctly formed (catches a per-clone state-number typo that variant FSM sims,
decode_verify, the slice-audit, and compile-check all miss).

Per wrapper, checks:
  - sync bytes 0xAA (state 0) + 0x55 (state 1) present
  - frame_valid (decode) OR gf_adder_param (compute) present
  - the frm next-state transitions include the full advance sequence 1..max
  - the advance sequence is COMPLETE: every state from 1 to max appears

What this deliberately does NOT check is the value of max. It used to require
max in (5, 6, 8) -- the three frame lengths that existed when this was written -- and
that criterion has flagged 40 of 93 wrappers since, keeping wrapper-fsm-sim.yml red
from 2026-07-09.

Every one of those 40 passes every structural check: sync bytes present, output present,
advance sequence complete. They differ only in being WIDER. A 128-bit format needs 16
code bytes and reaches max=19; binary256 and gf256 need 32 and reach max=35. That is
arithmetic, not a defect.

A criterion that lists the frame lengths it has seen is a snapshot of the world, not a
property of the design. The property is that the frame advances through every state it
declares, and that is what is checked.

  python3 conformance/wrapper_fsm_audit.py
"""
import re, glob, sys, os

_LAST = {}


def audit_one(path):
    """Verdict for one wrapper, by running the sweep and reading its result."""
    main()
    return _LAST.get(os.path.basename(path))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRAPPERS = (
    [w for w in glob.glob(os.path.join(ROOT, "fpga/openxc7-synth/corona_decode_*_ax7203.v"))
     if "corona_decode_top" not in w]
    + glob.glob(os.path.join(ROOT, "fpga/vivado/gf*_clean_ax7203.v"))
)


def main():
    bad = 0
    for w in sorted(WRAPPERS):
        src = open(w).read()
        name = os.path.basename(w)
        has_sync = ("8'hAA" in src) and ("8'h55" in src)
        has_out = ("frame_valid" in src) or ("gf_adder_param" in src)
        # frm next-state values (advance + wrap). Handles both forms:
        #   frm<=(rx_byte==8'hAA)?3'd1:3'd0   (sync, sized)
        #   frm<=3 / frm <= 3'd3              (data, unsized or sized, maybe spaced)
        nexts = set()
        for m in re.finditer(r"frm\s*<=\s*(?:\([^)]*\)\s*\?)?\s*(?:\d+'d)?(\d+)", src):
            nexts.add(int(m.group(1)))
        mx = max(nexts) if nexts else -1
        advance_ok = all(s in nexts for s in range(1, mx + 1))
        # No mx allow-list. See the module docstring: requiring mx in (5, 6, 8)
        # flagged every format wider than the three that existed when it was written.
        ok = has_sync and has_out and advance_ok and mx > 0
        _LAST[name] = ok
        if not ok:
            bad += 1
        print(f"{'OK   ' if ok else 'CHECK'} {name:42} max={mx} advance1..{mx}={'y' if advance_ok else 'N'} "
              f"sync={'y' if has_sync else 'N'} out={'y' if has_out else 'N'}")
    print(f"WRAPPER FSM AUDIT: {bad} need review / {len(WRAPPERS)} wrappers")
    print(f"COVERAGE: {len(WRAPPERS)} wrappers")
    return 1 if bad else 0


def self_check():
    """Loosening a criterion can empty it. This proves it did not.

    A state is removed from one wrapper's advance chain in a temporary copy, and the
    audit must report it. Without this, replacing the max allow-list with "the advance
    sequence is complete" would be indistinguishable from replacing it with nothing.
    """
    import re as _re, tempfile, shutil
    if not WRAPPERS:
        print("  no wrappers found -- nothing to test against")
        return 1
    victim = WRAPPERS[0]
    src = open(victim, encoding="utf-8", errors="replace").read()
    broken = _re.sub(r"3'd\d+:\s*begin[^\n]*\n", "", src, count=1)
    if broken == src:
        print(f"  could not remove a state from {os.path.basename(victim)}")
        return 1
    with tempfile.TemporaryDirectory() as td:
        keep = os.path.join(td, "orig.v")
        shutil.copy(victim, keep)
        open(victim, "w", encoding="utf-8").write(broken)
        try:
            caught = audit_one(victim) is False
        finally:
            shutil.copy(keep, victim)
    print(f"  a wrapper missing one advance state is flagged -> {caught}")
    print(f"\nself-check: {'PASS' if caught else 'FAIL -- the criterion is empty'}")
    return 0 if caught else 1


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        raise SystemExit(self_check())
    sys.exit(main())
