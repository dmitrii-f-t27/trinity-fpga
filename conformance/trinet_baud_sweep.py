#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trinet_baud_sweep.py — measure the board's actual bit rate, and CFGMCLK with it.

The node's UART divisor is fixed in the bitstream, so the board transmits at
exactly CFGMCLK / BAUD_DIV whatever the host asks for. Sweeping the host rate
and recording where the link still works brackets that number: the link holds
while the host is within a few percent of the board, and fails outside it, so
the centre of the working window is the board's real rate.

That matters because CFGMCLK is an internal RC oscillator known only as
"about 69-70 MHz". Everything about raising the transport ceiling depends on
knowing it better than that — at a small divisor, a 1.4% frequency uncertainty
plus divisor quantisation is the difference between a working link and a dead
one.

Usage:
    python3 trinet_baud_sweep.py --port /dev/cu.usbserial-1110
    python3 trinet_baud_sweep.py --port ... --centre 160000 --span 0.12

Author: Dmitrii Vasilev (@gHashTag)
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trinet_mac32_conformance_ax7203 import (  # noqa: E402
    OP_MAC32, generate_vectors, golden_dot, build_request,
)

RESP_LEN_V1 = 15
RESP_LEN_V2 = 19


def link_works(port, baud, resp_len, trials=6):
    """Does the board answer correctly at this host rate?

    Only the dot product is checked, not the tag: the question here is whether
    the bytes survive the wire, and a tag mismatch caused by one flipped bit
    would be reported the same way as a framing failure.
    """
    import serial
    try:
        ser = serial.Serial(port, baud, timeout=1)
    except Exception:
        return 0, trials
    ser.reset_input_buffer()
    ok = 0
    for nonce, w, x in generate_vectors(trials):
        try:
            ser.write(build_request(OP_MAC32, nonce, w, x))
            raw = ser.read(resp_len)
        except Exception:
            break
        if len(raw) == resp_len and raw[0] == 0xA5:
            y = raw[1] - 256 if raw[1] > 127 else raw[1]
            if y == golden_dot(w, x) and raw[3:7] == nonce:
                ok += 1
    ser.close()
    return ok, trials


def main():
    ap = argparse.ArgumentParser(description="bracket the board's real UART bit rate")
    ap.add_argument("--port", default="/dev/cu.usbserial-1110")
    ap.add_argument("--centre", type=int, default=160000,
                    help="nominal rate the bitstream was built for")
    ap.add_argument("--span", type=float, default=0.10,
                    help="fractional range to sweep either side of centre")
    ap.add_argument("--steps", type=int, default=41)
    ap.add_argument("--divisor", type=int, default=434,
                    help="BAUD_DIV compiled into the bitstream, to derive CFGMCLK")
    ap.add_argument("--v1", action="store_true", help="board runs the CRC cell (15-byte response)")
    a = ap.parse_args()

    resp_len = RESP_LEN_V1 if a.v1 else RESP_LEN_V2

    lo = int(a.centre * (1 - a.span))
    hi = int(a.centre * (1 + a.span))
    step = max(1, (hi - lo) // (a.steps - 1))

    print(f"sweeping {lo}..{hi} baud in {step} steps, {resp_len}-byte responses")
    print()

    working = []
    for baud in range(lo, hi + 1, step):
        ok, total = link_works(a.port, baud, resp_len)
        mark = "ok " if ok == total else ("part" if ok else "    ")
        bar = "#" * ok
        print(f"  {baud:8d}  {mark} {ok}/{total} {bar}")
        if ok == total:
            working.append(baud)

    print()
    if not working:
        print("RESULT: the link did not work anywhere in this range.")
        print("Either the sweep missed the board's rate, or the board is not")
        print("running a cell that speaks this response width.")
        return 1

    w_lo, w_hi = min(working), max(working)
    centre = (w_lo + w_hi) / 2
    tolerance = (w_hi - w_lo) / 2 / centre * 100
    cfgmclk = centre * a.divisor

    print(f"working window : {w_lo} .. {w_hi} baud")
    print(f"centre         : {centre:.0f} baud  (+/- {tolerance:.2f}% tolerated)")
    print(f"implied CFGMCLK: {cfgmclk/1e6:.3f} MHz  (centre x BAUD_DIV {a.divisor})")
    print()

    if w_lo == lo or w_hi == hi:
        print("WARNING: the window touches the edge of the sweep, so the centre is")
        print("a lower bound on accuracy. Re-run with a wider --span.")

    print("Divisors this CFGMCLK would support, with the exact host rate to use:")
    for div in (434, 300, 200, 120, 90, 60, 45, 30):
        rate = cfgmclk / div
        # A UART frame tolerates roughly 2-3% total error across ten bits; the
        # divisor's own quantisation eats into that budget before the host's
        # rate error is counted at all.
        quant = 1.0 / div * 100
        verdict = "comfortable" if quant < 1.0 else ("tight" if quant < 2.0 else "likely unstable")
        print(f"  BAUD_DIV={div:4d} -> {rate/1000:8.1f} kbaud   quantisation {quant:.2f}%  {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
