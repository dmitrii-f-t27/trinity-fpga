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

# Rates worth trying: the historical default, the corrected divisor-434 rate,
# and the three fast divisors built for the baud ladder.
CANDIDATE_RATES = [2372533, 1186267, 593133, 164000, 160000]

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


def main():
    ap = argparse.ArgumentParser(description="discover TRI-NET nodes on the bus")
    ap.add_argument("--ports", nargs="*", default=None)
    a = ap.parse_args()

    ports = a.ports or sorted(glob.glob("/dev/cu.usbserial*"))
    print(f"probing {len(ports)} port(s)\n")

    found = []
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
            print(f"  {p:<36} NODE  id {nid:#010x} ({name}), {baud} baud, {frame}")
            found.append((p, nid, baud))
        else:
            print(f"  {p:<36} —     no node answered at any candidate rate")

    print()
    if not found:
        print("No nodes found. A port with no node is normal: JTAG programmers")
        print("appear as serial ports too, and a board with no TRI-NET bitstream")
        print("will not answer.")
        return 1

    ids = [n for _, n, _ in found]
    print(f"{len(found)} node(s) responding")
    if len(set(ids)) != len(ids):
        print("WARNING: two boards report the SAME identity. The ledger credits")
        print("work to the node it dispatched to and refuses receipts claiming")
        print("another id, so they cannot both be paid. Reflash one with a")
        print("different NODE_ID before running them together.")
        return 1

    rates = {b for _, _, b in found}
    if len(rates) > 1:
        print(f"note: nodes are at different line rates {sorted(rates)} — the")
        print("coordinator opens each port at its own rate, so this is workable,")
        print("but a uniform fleet is easier to reason about.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
