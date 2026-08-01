#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trinet_mac32_conformance_ax7203.py — TRI-NET node conformance host.

Drives `fpga/vivado/trinet_mac32_ax7203.v` on an ALINX AX7203 (XC7A200T) over
the on-board CP2102N UART bridge and checks, for every job, that

  1. the ternary dot product returned by the FPGA equals an independent
     integer golden oracle computed here in Python, and
  2. the CRC-32 receipt tag returned by the FPGA equals `zlib.crc32` over the
     26-byte receipt preimage.

Check 2 is what makes the result a *receipt* rather than just a number: the tag
binds the answer to the exact job bytes, the nonce and the node identity, so a
node that returns the right number with the wrong tag, or the right tag for a
different job, is rejected.

Honesty note: CRC-32 is a checksum, not a signature. It proves the response is
internally consistent with the job. It does NOT prove the work ran on this
particular silicon, and it is not forgery-resistant against an adversary who
knows the scheme — any host can compute the same tag. Physical binding and
unforgeability are separate layers; see docs/TRI_NET_ARCHITECTURE.md.

TRIT ENCODING (TF3 packed, 2 bits per trit, LSB-first within a byte):
    0b00 =  0
    0b01 = +1
    0b10 = -1
    0b11 =  0   (reserved code, canonicalised to zero)

REQUEST  (24 bytes): AA 55 OP NONCE[4] W[8] X[8] TRIG
RESPONSE (15 bytes): A5 Y STATUS NONCE[4] NODE_ID[4] CRC[4]

Usage:
    python3 trinet_mac32_conformance_ax7203.py --self-test
    python3 trinet_mac32_conformance_ax7203.py --port /dev/cu.usbserial-1110 --n 512

Author: Dmitrii Vasilev (@gHashTag)
"""

import argparse
import random
import sys
import zlib

MAGIC_REQ = bytes([0xAA, 0x55])
MAGIC_RESP = 0xA5
OP_MAC32 = 0x01
STATUS_OK = 0x01
DEFAULT_NODE_ID = 0x5452494E  # "TRIN"

N_TRITS = 32
N_BYTES = N_TRITS // 4  # 4 trits per byte

TRIT_VALUE = {0b00: 0, 0b01: +1, 0b10: -1, 0b11: 0}


# ---------------------------------------------------------------------------
# Golden oracle
# ---------------------------------------------------------------------------

def unpack_trits(packed: bytes):
    """Unpack N_BYTES little-endian bytes into N_TRITS values in {-1, 0, +1}."""
    bus = int.from_bytes(packed, "little")
    return [TRIT_VALUE[(bus >> (2 * i)) & 0b11] for i in range(N_TRITS)]


def pack_trits(trits) -> bytes:
    """Pack N_TRITS values in {-1, 0, +1} into N_BYTES little-endian bytes."""
    code_of = {0: 0b00, +1: 0b01, -1: 0b10}
    bus = 0
    for i, t in enumerate(trits):
        bus |= code_of[t] << (2 * i)
    return bus.to_bytes(N_BYTES, "little")


def golden_dot(w_bytes: bytes, x_bytes: bytes) -> int:
    """Exact integer ternary dot product. Range [-32, +32]."""
    w = unpack_trits(w_bytes)
    x = unpack_trits(x_bytes)
    return sum(wi * xi for wi, xi in zip(w, x))


def receipt_preimage(op: int, nonce: bytes, w_bytes: bytes, x_bytes: bytes,
                     y: int, node_id: int) -> bytes:
    """The 26-byte sequence the RTL feeds through its CRC engine."""
    return (bytes([op & 0xFF])
            + nonce
            + w_bytes
            + x_bytes
            + bytes([y & 0xFF])
            + node_id.to_bytes(4, "little"))


def golden_receipt_tag(op: int, nonce: bytes, w_bytes: bytes, x_bytes: bytes,
                       y: int, node_id: int) -> int:
    return zlib.crc32(receipt_preimage(op, nonce, w_bytes, x_bytes, y, node_id)) & 0xFFFFFFFF


# ---------------------------------------------------------------------------
# Keyed receipt tag — SipHash-2-4
#
# The CRC tag above proves a response is self-consistent. It proves nothing
# about who produced it, because anyone can compute it. The keyed tag can only
# be produced by a key holder. Implemented here rather than pulled from a
# dependency so the conformance corpus stays self-contained, and checked
# against the published vectors in _siphash_self_test.
# ---------------------------------------------------------------------------

_M64 = (1 << 64) - 1


def _rotl64(x: int, n: int) -> int:
    return ((x << n) | (x >> (64 - n))) & _M64


def siphash24(msg: bytes, key: bytes) -> int:
    assert len(key) == 16
    k0 = int.from_bytes(key[:8], "little")
    k1 = int.from_bytes(key[8:], "little")
    v0 = k0 ^ 0x736F6D6570736575
    v1 = k1 ^ 0x646F72616E646F6D
    v2 = k0 ^ 0x6C7967656E657261
    v3 = k1 ^ 0x7465646279746573

    def rounds(n):
        nonlocal v0, v1, v2, v3
        for _ in range(n):
            v0 = (v0 + v1) & _M64
            v1 = _rotl64(v1, 13) ^ v0
            v0 = _rotl64(v0, 32)
            v2 = (v2 + v3) & _M64
            v3 = _rotl64(v3, 16) ^ v2
            v0 = (v0 + v3) & _M64
            v3 = _rotl64(v3, 21) ^ v0
            v2 = (v2 + v1) & _M64
            v1 = _rotl64(v1, 17) ^ v2
            v2 = _rotl64(v2, 32)

    full = len(msg) // 8 * 8
    for off in range(0, full, 8):
        m = int.from_bytes(msg[off:off + 8], "little")
        v3 ^= m
        rounds(2)
        v0 ^= m

    tail = int.from_bytes(msg[full:], "little") | ((len(msg) & 0xFF) << 56)
    v3 ^= tail
    rounds(2)
    v0 ^= tail

    v2 ^= 0xFF
    rounds(4)
    return v0 ^ v1 ^ v2 ^ v3


def golden_receipt_tag_keyed(op: int, nonce: bytes, w_bytes: bytes, x_bytes: bytes,
                             y: int, node_id: int, key: bytes) -> int:
    return siphash24(receipt_preimage(op, nonce, w_bytes, x_bytes, y, node_id), key)


def verify_receipt(job, response) -> tuple:
    """Independently verify a (job, response) pair.

    job      = dict(op, nonce, w, x)
    response = dict(y, status, nonce, node_id, crc)

    Returns (ok: bool, reason: str). This is the exact check a TRI-NET
    settlement layer runs before crediting work.
    """
    if response["status"] != STATUS_OK:
        return False, f"status {response['status']:#04x} != ok"
    if response["nonce"] != job["nonce"]:
        return False, "nonce mismatch (replay or crossed response)"
    expected_y = golden_dot(job["w"], job["x"])
    if response["y"] != expected_y:
        return False, f"result {response['y']} != golden {expected_y}"
    expected_crc = golden_receipt_tag(job["op"], job["nonce"], job["w"], job["x"],
                                      response["y"], response["node_id"])
    if response["crc"] != expected_crc:
        return False, f"receipt tag {response['crc']:#010x} != {expected_crc:#010x}"
    return True, "ok"


# ---------------------------------------------------------------------------
# Wire encoding
# ---------------------------------------------------------------------------

def build_request(op: int, nonce: bytes, w_bytes: bytes, x_bytes: bytes) -> bytes:
    assert len(nonce) == 4 and len(w_bytes) == N_BYTES and len(x_bytes) == N_BYTES
    return MAGIC_REQ + bytes([op & 0xFF]) + nonce + w_bytes + x_bytes + bytes([0x00])


def parse_response(raw: bytes):
    if len(raw) < 15 or raw[0] != MAGIC_RESP:
        return None
    y = raw[1] - 256 if raw[1] > 127 else raw[1]   # int8 two's complement
    return {
        "y": y,
        "status": raw[2],
        "nonce": raw[3:7],
        "node_id": int.from_bytes(raw[7:11], "little"),
        "crc": int.from_bytes(raw[11:15], "little"),
    }


# ---------------------------------------------------------------------------
# Self-test (no hardware)
# ---------------------------------------------------------------------------

def self_test() -> bool:
    print("self-test: trinet_mac32 golden oracle + receipt tag")
    failures = 0

    # 1. Trit round trip, including the reserved code.
    for code, val in TRIT_VALUE.items():
        packed = (code << 0).to_bytes(N_BYTES, "little")
        if unpack_trits(packed)[0] != val:
            print(f"  FAIL trit decode {code:#04b} -> {unpack_trits(packed)[0]} != {val}")
            failures += 1
    print("  trit decode table: ok (0b11 canonicalises to 0)")

    # 2. Hand-checked dot products.
    zeros = pack_trits([0] * N_TRITS)
    ones = pack_trits([+1] * N_TRITS)
    minus = pack_trits([-1] * N_TRITS)
    alt = pack_trits([+1 if i % 2 == 0 else -1 for i in range(N_TRITS)])

    cases = [
        (ones, ones, +32, "all +1 . all +1"),
        (ones, minus, -32, "all +1 . all -1"),
        (minus, minus, +32, "all -1 . all -1"),
        (zeros, ones, 0, "all 0 . all +1"),
        (alt, alt, +32, "alternating . itself"),
        (alt, ones, 0, "alternating . all +1"),
    ]
    for w, x, expect, name in cases:
        got = golden_dot(w, x)
        flag = "ok" if got == expect else "FAIL"
        if got != expect:
            failures += 1
        print(f"  dot {name:28s} = {got:+3d} (expect {expect:+3d}) {flag}")

    # 3. Reserved code 0b11 must behave as zero.
    all_reserved = (int("11" * N_TRITS, 2)).to_bytes(N_BYTES, "little")
    if golden_dot(all_reserved, ones) != 0:
        print("  FAIL reserved code 0b11 did not act as zero")
        failures += 1
    else:
        print("  reserved code 0b11 acts as zero: ok")

    # 4. Receipt tag is deterministic and input-sensitive.
    nonce = bytes([0xDE, 0xAD, 0xBE, 0xEF])
    tag_a = golden_receipt_tag(OP_MAC32, nonce, ones, ones, 32, DEFAULT_NODE_ID)
    tag_b = golden_receipt_tag(OP_MAC32, nonce, ones, ones, 32, DEFAULT_NODE_ID)
    tag_c = golden_receipt_tag(OP_MAC32, nonce, ones, ones, 31, DEFAULT_NODE_ID)
    tag_d = golden_receipt_tag(OP_MAC32, nonce, ones, ones, 32, DEFAULT_NODE_ID + 1)
    tag_e = golden_receipt_tag(OP_MAC32, bytes([0, 0, 0, 0]), ones, ones, 32, DEFAULT_NODE_ID)
    if tag_a != tag_b:
        print("  FAIL receipt tag not deterministic"); failures += 1
    for label, other in (("wrong result", tag_c), ("wrong node", tag_d), ("wrong nonce", tag_e)):
        if other == tag_a:
            print(f"  FAIL receipt tag collides on {label}"); failures += 1
    print(f"  receipt tag {tag_a:#010x}: deterministic, sensitive to result/node/nonce: ok")

    # 5. verify_receipt accepts a good pair and rejects tampering.
    job = {"op": OP_MAC32, "nonce": nonce, "w": ones, "x": alt}
    y = golden_dot(ones, alt)
    good = {"y": y, "status": STATUS_OK, "nonce": nonce, "node_id": DEFAULT_NODE_ID,
            "crc": golden_receipt_tag(OP_MAC32, nonce, ones, alt, y, DEFAULT_NODE_ID)}
    ok, reason = verify_receipt(job, good)
    if not ok:
        print(f"  FAIL verifier rejected a valid receipt: {reason}"); failures += 1
    else:
        print("  verifier accepts a valid receipt: ok")

    for label, mutate in (
        ("forged result", lambda r: {**r, "y": r["y"] + 1}),
        ("forged tag", lambda r: {**r, "crc": r["crc"] ^ 1}),
        ("replayed nonce", lambda r: {**r, "nonce": bytes([1, 2, 3, 4])}),
        ("impersonated node", lambda r: {**r, "node_id": DEFAULT_NODE_ID + 7}),
    ):
        ok, _ = verify_receipt(job, mutate(good))
        if ok:
            print(f"  FAIL verifier accepted a {label}"); failures += 1
        else:
            print(f"  verifier rejects {label}: ok")

    # 6. The keyed tag must reproduce the published SipHash-2-4 vectors, and
    #    the same values the RTL and the Zig side produce.
    ref_key = bytes(range(16))
    for msg_len, expect in ((0, 0x726FDB47DD0E0E31), (3, 0x85676696D7FB7E2D),
                            (26, 0x17D835B85BBB15F3)):
        got = siphash24(bytes(range(msg_len)), ref_key)
        if got != expect:
            print(f"  FAIL siphash24 len={msg_len}: {got:#018x} != {expect:#018x}")
            failures += 1
    print("  siphash-2-4 reproduces the published vectors: ok")

    keyed_a = golden_receipt_tag_keyed(OP_MAC32, nonce, ones, alt, y, DEFAULT_NODE_ID, ref_key)
    keyed_b = golden_receipt_tag_keyed(OP_MAC32, nonce, ones, alt, y, DEFAULT_NODE_ID, bytes([0xA5] * 16))
    if keyed_a == keyed_b:
        print("  FAIL keyed tag does not depend on the key")
        failures += 1
    else:
        print(f"  keyed receipt tag {keyed_a:#018x}: depends on the key: ok")

    # 7. Random cross-check of packing.
    rng = random.Random(0xF1B0)
    for _ in range(2000):
        trits = [rng.choice([-1, 0, +1]) for _ in range(N_TRITS)]
        if unpack_trits(pack_trits(trits)) != trits:
            print("  FAIL pack/unpack round trip"); failures += 1
            break
    else:
        print("  pack/unpack round trip over 2000 random vectors: ok")

    print(f"self-test: {'PASS' if failures == 0 else f'FAIL ({failures} failures)'}")
    return failures == 0


# ---------------------------------------------------------------------------
# Vector generation (shared with the iverilog testbench)
# ---------------------------------------------------------------------------

def generate_vectors(n: int, seed: int = 0x7213):
    """Deterministic job vectors. The first cases are the structural corners."""
    rng = random.Random(seed)
    zeros = pack_trits([0] * N_TRITS)
    ones = pack_trits([+1] * N_TRITS)
    minus = pack_trits([-1] * N_TRITS)
    alt = pack_trits([+1 if i % 2 == 0 else -1 for i in range(N_TRITS)])
    reserved = (int("11" * N_TRITS, 2)).to_bytes(N_BYTES, "little")

    corners = [
        (zeros, zeros), (ones, ones), (minus, minus), (ones, minus),
        (zeros, ones), (alt, alt), (alt, ones), (reserved, ones),
        (reserved, reserved), (ones, alt),
    ]
    vectors = []
    for i, (w, x) in enumerate(corners[:n]):
        vectors.append((i.to_bytes(4, "little"), w, x))
    for i in range(len(vectors), n):
        w = pack_trits([rng.choice([-1, 0, +1]) for _ in range(N_TRITS)])
        x = pack_trits([rng.choice([-1, 0, +1]) for _ in range(N_TRITS)])
        vectors.append((i.to_bytes(4, "little"), w, x))
    return vectors


def emit_hex_vectors(path: str, n: int, node_id: int):
    """Write vectors for the iverilog testbench: one job per line.

    Line format (hex, no 0x): NONCE W X Y CRC
    W and X are 16 hex digits each (8 bytes, little-endian as transmitted).
    """
    with open(path, "w") as fh:
        for nonce, w, x in generate_vectors(n):
            y = golden_dot(w, x)
            crc = golden_receipt_tag(OP_MAC32, nonce, w, x, y, node_id)
            fh.write("%s %s %s %02x %08x\n" % (
                nonce.hex(), w.hex(), x.hex(), y & 0xFF, crc))
    print(f"wrote {n} vectors to {path}")


# ---------------------------------------------------------------------------
# Hardware run
# ---------------------------------------------------------------------------

def run_hw(port: str, baud: int, n: int, node_id: int, verbose: bool) -> bool:
    import serial

    ser = serial.Serial(port, baud, timeout=2)
    ser.reset_input_buffer()

    ok = 0
    fails = []
    seen_node_ids = set()

    for nonce, w, x in generate_vectors(n):
        ser.write(build_request(OP_MAC32, nonce, w, x))
        raw = ser.read(15)
        resp = parse_response(raw)
        if resp is None:
            fails.append(f"nonce={nonce.hex()} no/short response ({len(raw)} bytes)")
            continue
        seen_node_ids.add(resp["node_id"])
        job = {"op": OP_MAC32, "nonce": nonce, "w": w, "x": x}
        good, reason = verify_receipt(job, resp)
        if good:
            ok += 1
            if verbose:
                print(f"  nonce={nonce.hex()} y={resp['y']:+3d} "
                      f"node={resp['node_id']:#010x} crc={resp['crc']:#010x} ok")
        else:
            fails.append(f"nonce={nonce.hex()} {reason}")

    ser.close()

    print(f"HW RESULT: {ok}/{n} receipts verified (fails={len(fails)})")
    for f in fails[:20]:
        print(f"  {f}")
    if len(fails) > 20:
        print(f"  ... and {len(fails) - 20} more")
    if seen_node_ids:
        print("node ids seen: " + ", ".join(f"{i:#010x}" for i in sorted(seen_node_ids)))
    if node_id not in seen_node_ids and seen_node_ids:
        print(f"WARNING: expected node id {node_id:#010x} was not reported by the board")
    return ok == n


def main():
    ap = argparse.ArgumentParser(description="TRI-NET MAC32 node conformance for AX7203")
    ap.add_argument("--port", default="/dev/cu.usbserial-1110")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=512)
    ap.add_argument("--node-id", type=lambda s: int(s, 0), default=DEFAULT_NODE_ID)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--emit-vectors", metavar="PATH",
                    help="write golden vectors for the iverilog testbench and exit")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        sys.exit(0 if self_test() else 1)
    if a.emit_vectors:
        emit_hex_vectors(a.emit_vectors, a.n, a.node_id)
        sys.exit(0)
    sys.exit(0 if run_hw(a.port, a.baud, a.n, a.node_id, a.verbose) else 1)


if __name__ == "__main__":
    main()
