#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trinet_dna_probe_host.py — read the factory device DNA over UART.

Answers the measurable half of "can a TRI-NET receipt be bound to this chip":
whether the open toolchain can reach DNA_PORT at all, and what this particular
board reports.

Honesty note: device DNA is an identifier, not a secret. It is readable over
JTAG and by any bitstream loaded on the part, so a value read once can be
claimed by software forever. A receipt bound to the DNA proves that a bitstream
asserted an identity — not that the arithmetic ran on that chip.

REQUEST  (4 bytes):  AA 55 OP TRIG
RESPONSE (11 bytes): A5 STATUS DNA[8] BITS

Usage:
    python3 trinet_dna_probe_host.py --port /dev/cu.usbserial-1110

Author: Dmitrii Vasilev (@gHashTag)
"""

import argparse
import sys

FRAME = bytes([0xAA, 0x55])
OP_READ_DNA = 0x10
RESP_LEN = 11


def read_dna(ser):
    ser.write(FRAME + bytes([OP_READ_DNA, 0x00]))
    raw = ser.read(RESP_LEN)
    if len(raw) < RESP_LEN or raw[0] != 0xA5:
        return None
    return {
        "status": raw[1],
        "dna": int.from_bytes(raw[2:10], "little"),
        "bits": raw[10],
    }


def main():
    ap = argparse.ArgumentParser(description="read the AX7203 device DNA")
    ap.add_argument("--port", default="/dev/cu.usbserial-1110")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--reads", type=int, default=8)
    a = ap.parse_args()

    import serial
    ser = serial.Serial(a.port, a.baud, timeout=2)
    ser.reset_input_buffer()

    seen = set()
    ok = 0
    bits = 0
    for _ in range(a.reads):
        r = read_dna(ser)
        if r is None or r["status"] != 0x01:
            continue
        ok += 1
        seen.add(r["dna"])
        bits = r["bits"]
    ser.close()

    print(f"successful reads: {ok}/{a.reads}")
    if not seen:
        print("RESULT: no DNA returned — either the probe is not flashed, or "
              "DNA_PORT is not reachable on this part")
        return 1

    for d in sorted(seen):
        print(f"  device DNA: 0x{d:016x}  ({bits} significant bits)")

    # A device identifier that is not stable across reads is not an identifier.
    if len(seen) != 1:
        print("RESULT: the value CHANGED between reads — this is not a stable "
              "device identifier and must not be used as one")
        return 1

    dna = next(iter(seen))
    if dna == 0:
        print("RESULT: DNA reads as zero — the primitive routed but returns "
              "nothing usable on this part")
        return 1

    print(f"RESULT: stable, non-zero device DNA over {ok} reads. A node id "
          f"derived from it would be 0x{dna & 0xFFFFFFFF:08x}.")
    print("Reminder: this is an identifier, not a secret. It stops two boards "
          "sharing an id; it does not stop software claiming one it has seen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
