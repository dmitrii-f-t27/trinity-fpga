#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trinet_discover.py — find which serial ports are TRI-NET nodes, and at what rate.

With several boards attached, the useful first question is not "does this one
work" but "what is on each port, and which of them are even boards". Some of
the ports on the bus belong to JTAG programmers rather than to a node, and a
board may be carrying any of the bitstreams built so far, at any of the line
rates. Probing that with a full conformance run costs minutes per port.

This tries one job per (port, rate) with a short timeout and reports what
answered, what identity it claimed, and how fast it is talking.

Usage:
    python3 trinet_discover.py
    python3 trinet_discover.py --ports /dev/cu.usbserial-110 /dev/cu.usbserial-130

Author: Dmitrii Vasilev (@gHashTag)
"""

import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trinet_mac32_conformance_ax7203 import (  # noqa: E402
    OP_MAC32, generate_vectors, golden_dot, build_request,
)

# Rates worth trying, to ACQUIRE a board — not to operate it.
#
# CFGMCLK is an untrimmed RC oscillator, so the line rate is a property of the
# individual die. Measured on this fleet with trinet_baud_sweep.py on
# 2026-08-03: 70.464, 67.131 and 68.685 MHz, so at BAUD_DIV=60 the boards speak
# 1174399, 1118846 and 1144744 baud. A 4.97% spread.
#
# The spread does NOT force a rate per board. Each board tolerates roughly
# +/-4.5% and the three windows overlap on 1121020..1168468, so 1144744 reaches
# all three: 6400 jobs each, zero failures. That rate leads the list.
#
# The important part is what this list cannot do. A single job answered at a
# rate proves the rate is close enough to acquire the board, not that it is
# close enough to work: node2 answers 97.6% of jobs at 1186267 and 100% at
# 1144744, and one probe cannot tell those apart. So after acquiring, this tool
# measures — see confirm() — rather than reporting the first rate that replied.
CANDIDATE_RATES = [
    1144744,   # BAUD_DIV=60, measured intersection of all three windows
    1174399,   # BAUD_DIV=60, node0's own centre
    1118846,   # BAUD_DIV=60, node1's own centre
    1186267,   # BAUD_DIV=60, the fleet constant this project used to assume
    2372533,   # BAUD_DIV=30
    593133,    # BAUD_DIV=120
    164000, 160000,   # BAUD_DIV=434, historical
]

# Jobs used to judge an acquired rate. Six was the old figure and it is useless
# here: a rate losing 2.4% of jobs passes six in a row 86% of the time.
CONFIRM_JOBS = 64

# Identities the fleet build assigns, so a board can name itself.
KNOWN_IDS = {
    0x5452494E: "node0",
    0x5452494F: "node1",
    0x54524950: "node2",
}


def try_one(port, baud, timeout=0.25):
    """One job. Returns (claimed_id, response_len) or None."""
    import serial
    try:
        ser = serial.Serial(port, baud, timeout=timeout)
    except Exception:
        return None
    try:
        ser.reset_input_buffer()
        nonce, w, x = next(iter(generate_vectors(2)[1:]))
        ser.write(build_request(OP_MAC32, nonce, w, x))
        raw = ser.read(19)
        if len(raw) < 15 or raw[0] != 0xA5:
            return None
        y = raw[1] - 256 if raw[1] > 127 else raw[1]
        if y != golden_dot(w, x) or raw[3:7] != nonce:
            return None
        # Bytes 0..10 are identical in both frame versions, so the identity is
        # readable before the tag width is known.
        return int.from_bytes(raw[7:11], "little"), len(raw)
    except Exception:
        return None
    finally:
        ser.close()


def confirm(port, baud, node_id, jobs=CONFIRM_JOBS, timeout=0.05):
    """How many of `jobs` come back with every predictable byte right.

    The tag is not checked — it needs the node's key, and this tool runs before
    anyone knows whether a key is held. Everything else is predictable, and a
    marginal rate damages those bytes as readily as it damages the tag.
    """
    import serial
    try:
        ser = serial.Serial(port, baud, timeout=timeout)
    except Exception:
        return 0, jobs
    clean = 0
    try:
        ser.reset_input_buffer()
        for nonce, w, x in generate_vectors(jobs):
            ser.write(build_request(OP_MAC32, nonce, w, x))
            raw = ser.read(19)
            if len(raw) < 15:
                continue
            expected = bytes([0xA5, golden_dot(w, x) & 0xFF, 0x01]) + nonce + \
                node_id.to_bytes(4, "little")
            if raw[:11] == expected:
                clean += 1
    except Exception:
        pass
    finally:
        ser.close()
    return clean, jobs


def main():
    ap = argparse.ArgumentParser(description="discover TRI-NET nodes on the bus")
    ap.add_argument("--ports", nargs="*", default=None)
    a = ap.parse_args()

    ports = a.ports or sorted(glob.glob("/dev/cu.usbserial*"))
    print(f"probing {len(ports)} port(s)\n")

    found = []
    marginal = []
    for p in ports:
        hit = None
        for baud in CANDIDATE_RATES:
            r = try_one(p, baud)
            if r:
                hit = (baud, r[0], r[1])
                break
        if hit:
            baud, nid, width = hit
            name = KNOWN_IDS.get(nid, "unknown identity")
            frame = "keyed (v2)" if width >= 19 else "crc (v1)"
            clean, jobs = confirm(p, baud, nid)
            pct = 100.0 * clean / jobs
            print(f"  {p:<36} NODE  id {nid:#010x} ({name}), {baud} baud, {frame}, "
                  f"{clean}/{jobs} clean")
            found.append((p, nid, baud, pct))
            if clean < jobs:
                marginal.append((p, baud, pct))
        else:
            print(f"  {p:<36} —     no node answered at any candidate rate")

    print()
    if not found:
        print("No nodes found. A port with no node is normal: JTAG programmers")
        print("appear as serial ports too, and a board with no TRI-NET bitstream")
        print("will not answer.")
        return 1

    ids = [n for _, n, _, _ in found]
    print(f"{len(found)} node(s) responding")
    if len(set(ids)) != len(ids):
        print("WARNING: two boards report the SAME identity. The ledger credits")
        print("work to the node it dispatched to and refuses receipts claiming")
        print("another id, so they cannot both be paid. Reflash one with a")
        print("different NODE_ID before running them together.")
        return 1

    if marginal:
        print()
        print("WARNING: a board answered, but not on every job. That is the shape")
        print("of a host rate a few percent off the board's own, and it is NOT")
        print("evidence of a bad board, cable or hub — node2 read as 97.6% for a")
        print("day and delivers 6400/6400 once the rate is measured. Sweep it:")
        for p, baud, pct in marginal:
            print(f"  {p} at {baud} baud: {pct:.2f}% clean")
            print(f"    python3 conformance/trinet_baud_sweep.py --port {p} "
                  f"--centre {baud} --span 0.08")
        return 1

    rates = {b for _, _, b, _ in found}
    if len(rates) > 1:
        print(f"note: nodes are at different line rates {sorted(rates)} — the")
        print("coordinator opens each port at its own rate, so this is workable,")
        print("but a uniform fleet is easier to reason about.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
