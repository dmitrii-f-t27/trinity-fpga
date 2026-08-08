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

WHY THIS TOOL WAS REWRITTEN (2026-08-03)
----------------------------------------
The first version asked six jobs per rate and called the point good if all six
came back. Six is not enough to see the thing this measurement exists to find.
A rate that loses 2.4% of jobs passes 6/6 about 86% of the time, so the whole
degradation shoulder around a board's real rate read as "ok" — and the window
it printed was therefore wider than the truth, and its centre wrong.

That is not hypothetical. node2 was run at 1186267 baud, lost 2.4% of its jobs
for a day, and the loss was recorded as a link fault after a sweep concluded
the rate was not the cause. Measured with enough jobs per point, node2's clean
window is 1126954..1168473 and 1186267 is outside it: at 1147713 baud the same
board, same cable, same hub returns 6400/6400.

Two consequences are baked in here:

  * jobs per point is 64 by default, not 6, and a point counts as clean only if
    every job is clean. At a 2.4% loss that is a 21% chance of a false clean,
    against 86% before; the degradation shoulder is printed separately so a
    reader can see it either way rather than having it rounded into the window.
  * every predictable byte is checked, not just the product and the nonce. The
    old check would accept a frame whose node identity or status byte had been
    corrupted, which is precisely the kind of damage a marginal rate does.

Usage:
    python3 trinet_baud_sweep.py --port /dev/cu.usbserial-1110
    python3 trinet_baud_sweep.py --port ... --centre 1186267 --span 0.08

Author: Dmitrii Vasilev (@gHashTag)
"""

import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trinet_mac32_conformance_ax7203 import (  # noqa: E402
    MAGIC_RESP, OP_MAC32, generate_vectors, golden_dot, build_request,
)

RESP_LEN_V1 = 15
RESP_LEN_V2 = 19

STATUS_OK = 0x01
# A board that has not been keyed yet answers 0x04 NO_KEY and computes the dot
# product correctly. That is the state every board is in between a re-flash and
# `trinet setkey` — precisely when its line rate has to be measured — so a sweep
# that demands 0x01 reports a healthy fresh board as 0% clean at every rate and
# finds no window at all. Mirrors protocol.statusMeansComputed().
STATUS_COMPUTED = frozenset({0x01, 0x04})
HEAD_LEN = 11          # magic, y, status, nonce[4], node_id[4] — the tag needs the key


def probe(port, baud, resp_len, jobs, timeout):
    """Run `jobs` jobs at this host rate and return the raw heads with their truth.

    No verdict here. A rate is judged after the whole sweep, once the node's own
    identity is known — asking each point to also guess the identity would let a
    corrupted id byte define what a correct id looks like.
    """
    import serial
    try:
        ser = serial.Serial(port, baud, timeout=timeout)
    except Exception:
        return None
    out = []
    try:
        ser.reset_input_buffer()
        for nonce, w, x in generate_vectors(jobs):
            ser.write(build_request(OP_MAC32, nonce, w, x))
            raw = ser.read(resp_len)
            out.append((raw, nonce, golden_dot(w, x)))
    except Exception:
        pass
    finally:
        ser.close()
    return out


def modal_node_id(samples):
    """The identity the board claims when it is being heard correctly.

    Taken from frames that are otherwise perfect, so a run of corrupted frames
    at a bad rate cannot vote.
    """
    votes = collections.Counter()
    for results in samples:
        if not results:
            continue
        for raw, nonce, gy in results:
            if len(raw) >= HEAD_LEN and raw[0] == MAGIC_RESP \
                    and raw[2] in STATUS_COMPUTED \
                    and raw[3:7] == nonce and raw[1] == (gy & 0xFF):
                votes[int.from_bytes(raw[7:11], "little")] += 1
    return votes.most_common(1)[0][0] if votes else None


def judge(results, resp_len, node_id):
    """(clean, rx_bad, tx_bad, empty, short) for one rate."""
    clean = rx_bad = tx_bad = empty = short = 0
    for raw, nonce, gy in results:
        if len(raw) == 0:
            empty += 1
        elif len(raw) < resp_len:
            short += 1
        else:
            tail = nonce + node_id.to_bytes(4, "little")
            got = raw[:HEAD_LEN]
            status_ok = got[0] == MAGIC_RESP and got[2] in STATUS_COMPUTED
            if status_ok and got[1] == (gy & 0xFF) and got[3:11] == tail:
                clean += 1
            elif status_ok and got[3:11] == tail:
                # Nonce and identity survived, the product did not: the damage is
                # in the operands, so it happened host -> board.
                tx_bad += 1
            else:
                rx_bad += 1
    return clean, rx_bad, tx_bad, empty, short


def widest_clean_band(rows):
    """Longest run of consecutive fully-clean rates. Returns (lo_idx, hi_idx) or None."""
    best = None
    i = 0
    while i < len(rows):
        if rows[i][1] == rows[i][6]:      # clean == jobs
            j = i
            while j + 1 < len(rows) and rows[j + 1][1] == rows[j + 1][6]:
                j += 1
            if best is None or (j - i) > (best[1] - best[0]):
                best = (i, j)
            i = j + 1
        else:
            i += 1
    return best


def main():
    ap = argparse.ArgumentParser(description="bracket the board's real UART bit rate")
    ap.add_argument("--port", default="/dev/cu.usbserial-1110")
    ap.add_argument("--centre", type=int, default=1186267,
                    help="nominal rate the bitstream was built for")
    ap.add_argument("--span", type=float, default=0.08,
                    help="fractional range to sweep either side of centre")
    ap.add_argument("--steps", type=int, default=33)
    ap.add_argument("--jobs", type=int, default=64,
                    help="jobs per rate; six cannot tell a clean rate from a 2%% one")
    ap.add_argument("--timeout", type=float, default=0.05)
    ap.add_argument("--divisor", type=int, default=60,
                    help="BAUD_DIV compiled into the bitstream, to derive CFGMCLK")
    ap.add_argument("--v1", action="store_true",
                    help="board runs the CRC cell (15-byte response)")
    a = ap.parse_args()

    resp_len = RESP_LEN_V1 if a.v1 else RESP_LEN_V2

    lo = int(a.centre * (1 - a.span))
    hi = int(a.centre * (1 + a.span))
    step = max(1, (hi - lo) // (a.steps - 1))
    rates = list(range(lo, hi + 1, step))

    print(f"sweeping {lo}..{hi} baud in {len(rates)} steps of {step}, "
          f"{a.jobs} jobs per step, {resp_len}-byte responses")
    print()

    samples = [probe(a.port, b, resp_len, a.jobs, a.timeout) for b in rates]

    node_id = modal_node_id(samples)
    if node_id is None:
        print("RESULT: nothing answered correctly anywhere in this range.")
        print("Either the sweep missed the board's rate, or the board is not")
        print("running a cell that speaks this response width.")
        return 1
    print(f"board identity (from the frames that came through clean): {node_id:#010x}")
    print()

    print(f"{'baud':>9} {'clean':>7} {'clean%':>8} {'rx_bad':>7} {'tx_bad':>7} "
          f"{'empty':>6} {'short':>6}")
    rows = []
    for b, results in zip(rates, samples):
        if results is None:
            print(f"{b:>9}  port would not open at this rate")
            continue
        clean, rx_bad, tx_bad, empty, short = judge(results, resp_len, node_id)
        n = len(results)
        flag = "" if clean == n else ("  <- degraded" if clean else "")
        print(f"{b:>9} {clean:>7} {100.0*clean/n:>7.3f}% {rx_bad:>7} {tx_bad:>7} "
              f"{empty:>6} {short:>6}{flag}")
        rows.append((b, clean, rx_bad, tx_bad, empty, short, n))

    print()
    band = widest_clean_band(rows)
    if band is None:
        print("RESULT: no rate in this range delivered every job.")
        print("The board answers somewhere here but never cleanly — widen --span,")
        print("or suspect the cable rather than the rate.")
        return 1

    i, j = band
    w_lo, w_hi = rows[i][0], rows[j][0]
    centre = (w_lo + w_hi) / 2
    tolerance = (w_hi - w_lo) / 2 / centre * 100
    cfgmclk = centre * a.divisor

    # The degradation shoulder is the run of lossy rates that TOUCHES the clean
    # window, walking outward until a rate that delivers nothing. Rates further
    # out can also answer once or twice by luck; they are the far side of the
    # cliff, not a shoulder, and quoting their loss rate as the worst case makes
    # a marginal operating point look catastrophic instead of plausible — which
    # is the wrong lesson, because plausible is what made this bug survive.
    shoulder = []
    k = i - 1
    while k >= 0 and rows[k][1] > 0:
        shoulder.append(rows[k])
        k -= 1
    k = j + 1
    while k < len(rows) and rows[k][1] > 0:
        shoulder.append(rows[k])
        k += 1
    degraded = sorted(shoulder, key=lambda r: r[0])

    print(f"clean window   : {w_lo} .. {w_hi} baud  ({j - i + 1} consecutive steps, "
          f"{(j - i + 1) * a.jobs} jobs, no failures)")
    print(f"USE THIS RATE  : {centre:.0f} baud  (+/- {tolerance:.2f}% tolerated)")
    # The centre is only as sharp as the step that bracketed it, and CFGMCLK
    # inherits that. Printing six digits of a number known to half a percent is
    # how a measurement becomes a constant nobody rechecks.
    cfg_err = (step / 2) * a.divisor
    print(f"implied CFGMCLK: {cfgmclk/1e6:.2f} +/- {cfg_err/1e6:.2f} MHz  "
          f"(centre x BAUD_DIV {a.divisor}; the error is the sweep step, "
          f"re-run with more --steps to sharpen it)")
    # Each side is printed separately. A shoulder that degrades gently on one
    # side and cliffs on the other is a real asymmetry in the board, and merging
    # the two into one range with one worst-case figure hides it.
    for side, rs in (("below", [r for r in degraded if r[0] < w_lo]),
                     ("above", [r for r in degraded if r[0] > w_hi])):
        if not rs:
            continue
        pcts = [100.0 * r[1] / r[6] for r in rs]
        print(f"degraded {side:<5} : {min(r[0] for r in rs)} .. {max(r[0] for r in rs)} "
              f"baud — answers, but loses jobs ({min(pcts):.2f}%..{max(pcts):.2f}% clean)")
    if degraded:
        print("                 A rate in a degraded zone is the failure mode that")
        print("                 reads as a bad board, a bad cable or a bad hub. It is")
        print("                 none of those. Do not operate there.")
    print()

    if i == 0 or j == len(rows) - 1:
        print("WARNING: the window touches the edge of the sweep, so the centre is")
        print("a lower bound on accuracy. Re-run with a wider --span.")
        print()

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
