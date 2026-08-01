#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trinet_node_v2_conformance_ax7203.py — keyed-receipt node conformance.

Same ternary dot product as the v1 node, with the receipt tag upgraded from
CRC-32 to SipHash-2-4 under a key that exists only inside the bitstream.

The check that matters here is not just that the tag matches. It is that a tag
computed with the WRONG key does not — if it did, the key would not be reaching
the receipt and the upgrade would be decorative.

REQUEST  (24 bytes): AA 55 OP NONCE[4] W[8] X[8] TRIG
RESPONSE (19 bytes): A5 Y STATUS NONCE[4] NODE_ID[4] TAG[8]

Usage:
    python3 trinet_node_v2_conformance_ax7203.py --self-test
    python3 trinet_node_v2_conformance_ax7203.py --port /dev/cu.usbserial-1110 --n 256

Author: Dmitrii Vasilev (@gHashTag)
"""

import argparse
import os
import sys

# Importable from anywhere, not only from inside conformance/ — a host that
# only runs from one working directory is a host people run the wrong way.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trinet_mac32_conformance_ax7203 import (  # noqa: E402
    OP_MAC32, MAGIC_REQ, MAGIC_RESP, STATUS_OK, DEFAULT_NODE_ID,
    generate_vectors, golden_dot, golden_receipt_tag_keyed, build_request,
)

RESP_LEN = 19

# Matches the RTL default parameter RECEIPT_KEY. A deployment overrides both.
DEFAULT_KEY = bytes(range(16))


def parse_response(raw: bytes):
    if len(raw) < RESP_LEN or raw[0] != MAGIC_RESP:
        return None
    y = raw[1] - 256 if raw[1] > 127 else raw[1]
    return {
        "y": y,
        "status": raw[2],
        "nonce": raw[3:7],
        "node_id": int.from_bytes(raw[7:11], "little"),
        "tag": int.from_bytes(raw[11:19], "little"),
    }


def verify(job, resp, key):
    if resp["status"] != STATUS_OK:
        return False, f"status {resp['status']:#04x}"
    if resp["nonce"] != job["nonce"]:
        return False, "nonce mismatch"
    expected_y = golden_dot(job["w"], job["x"])
    if resp["y"] != expected_y:
        return False, f"result {resp['y']} != golden {expected_y}"
    expected = golden_receipt_tag_keyed(job["op"], job["nonce"], job["w"], job["x"],
                                        resp["y"], resp["node_id"], key)
    if resp["tag"] != expected:
        return False, f"keyed tag {resp['tag']:#018x} != {expected:#018x}"
    return True, "ok"


def self_test() -> bool:
    print("self-test: trinet node v2 keyed receipt")
    failures = 0
    key = DEFAULT_KEY
    wrong = bytes([b ^ 0xFF for b in key])

    for nonce, w, x in generate_vectors(8):
        y = golden_dot(w, x)
        good = golden_receipt_tag_keyed(OP_MAC32, nonce, w, x, y, DEFAULT_NODE_ID, key)
        bad = golden_receipt_tag_keyed(OP_MAC32, nonce, w, x, y, DEFAULT_NODE_ID, wrong)
        if good == bad:
            print(f"  FAIL nonce={nonce.hex()} the tag does not depend on the key")
            failures += 1
        resp = {"y": y, "status": STATUS_OK, "nonce": nonce,
                "node_id": DEFAULT_NODE_ID, "tag": good}
        job = {"op": OP_MAC32, "nonce": nonce, "w": w, "x": x}
        ok, reason = verify(job, resp, key)
        if not ok:
            print(f"  FAIL verifier rejected an honest receipt: {reason}")
            failures += 1
        ok_wrong, _ = verify(job, resp, wrong)
        if ok_wrong:
            print("  FAIL verifier accepted a receipt under the wrong key")
            failures += 1

    print(f"  8 vectors: honest accepted, wrong-key rejected, tag key-dependent: "
          f"{'ok' if failures == 0 else 'FAIL'}")
    print(f"self-test: {'PASS' if failures == 0 else 'FAIL'}")
    return failures == 0


def run_hw(port: str, baud: int, n: int, key: bytes) -> bool:
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    ser.reset_input_buffer()

    ok = 0
    fails = []
    ids = set()
    for nonce, w, x in generate_vectors(n):
        ser.write(build_request(OP_MAC32, nonce, w, x))
        resp = parse_response(ser.read(RESP_LEN))
        if resp is None:
            fails.append(f"nonce={nonce.hex()} no/short response")
            continue
        ids.add(resp["node_id"])
        job = {"op": OP_MAC32, "nonce": nonce, "w": w, "x": x}
        good, reason = verify(job, resp, key)
        if good:
            ok += 1
        else:
            fails.append(f"nonce={nonce.hex()} {reason}")
    ser.close()

    print(f"HW RESULT: {ok}/{n} keyed receipts verified (fails={len(fails)})")
    for f in fails[:10]:
        print(f"  {f}")
    if ids:
        print("node ids seen: " + ", ".join(f"{i:#010x}" for i in sorted(ids)))
        if 0 in ids:
            print("WARNING: a node id of zero means the DNA fallback did not engage")
    return ok == n


def main():
    ap = argparse.ArgumentParser(description="TRI-NET node v2 conformance")
    ap.add_argument("--port", default="/dev/cu.usbserial-1110")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=256)
    ap.add_argument("--key", default=None, help="16-byte receipt key as hex")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    key = bytes.fromhex(a.key) if a.key else DEFAULT_KEY
    if len(key) != 16:
        print("the receipt key must be 16 bytes")
        return 2

    if a.self_test:
        return 0 if self_test() else 1
    return 0 if run_hw(a.port, a.baud, a.n, key) else 1


if __name__ == "__main__":
    sys.exit(main())
