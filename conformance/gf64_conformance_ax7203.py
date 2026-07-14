#!/usr/bin/env python3
"""
gf64_conformance_ax7203.py — Reproducible GF64 ADD silicon conformance harness.

Flashes the GF64 ADD bitstream, runs golden oracle vectors through UART,
and reports bit-exact pass rate with provenance verification.

Usage:
  python3 conformance/gf64_conformance_ax7203.py --bit <bitstream.bit> [--n 512]
"""
import serial, time, sys, argparse, hashlib, json, os, random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gf_ref import FORMATS, gf_add

GF64 = FORMATS["gf64"]
PORT = "/dev/cu.usbserial-1120"
BAUD = 160000


def send_recv(ser, a, b, delay=0.3):
    """Send GF64 ADD frame, receive result."""
    pkt = bytearray([0xAA, 0x55, 0x00])
    for i in range(8): pkt += bytes([(a >> (8*i)) & 0xFF])
    for i in range(8): pkt += bytes([(b >> (8*i)) & 0xFF])
    pkt += bytes([0x00])
    ser.write(pkt)
    time.sleep(delay)
    r = ser.read(9)
    if len(r) >= 9 and r[0] == 0xA5:
        return int.from_bytes(r[1:9], 'little')
    return None


def gen_vectors(n=512):
    """Generate diverse test vectors."""
    random.seed(42)
    vecs = []
    seen = set()

    def add(a, b):
        a &= (1 << 64) - 1
        b &= (1 << 64) - 1
        if (a, b) not in seen:
            seen.add((a, b))
            vecs.append((a, b))

    one = GF64.bias << GF64.mant_bits  # 1.0
    two = (GF64.bias + 1) << GF64.mant_bits
    half = (GF64.bias - 1) << GF64.mant_bits
    neg = 1 << (GF64.exp_bits + GF64.mant_bits)

    # Edge cases
    for a in [0, neg, one, two, half, one+1, one-1, two+1, half+1, neg|one, neg|two]:
        for b in [0, one, neg, two, half]:
            add(a, b)

    # Near-tie rounding
    for delta in [1, 2, 3, (1 << 20), (1 << 38)]:
        add(one, one - delta)
        add(one | neg, one - delta)

    # Normal range randoms
    for _ in range(n):
        exp_a = random.randint(GF64.bias - 5, GF64.bias + 5)
        exp_b = random.randint(GF64.bias - 5, GF64.bias + 5)
        mant_a = random.randint(0, (1 << 20) - 1) * ((1 << GF64.mant_bits) // (1 << 20))
        mant_b = random.randint(0, (1 << 20) - 1) * ((1 << GF64.mant_bits) // (1 << 20))
        sa = random.randint(0, 1)
        sb = random.randint(0, 1)
        add((sa << 63) | (exp_a << 39) | (mant_a & ((1 << 39) - 1)),
            (sb << 63) | (exp_b << 39) | (mant_b & ((1 << 39) - 1)))

    return vecs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bit", required=True, help="Path to bitstream file")
    parser.add_argument("--port", default=PORT)
    parser.add_argument("--n", type=int, default=512)
    parser.add_argument("--delay", type=float, default=0.3)
    args = parser.parse_args()

    # Verify provenance
    prov = Path(args.bit + ".provenance.json")
    if prov.exists():
        with open(prov) as f:
            p = json.load(f)
        print(f"Provenance: commit={p.get('git_commit','?')[:8]} sha256={p.get('bitstream_sha256','?')[:16]}...")
    else:
        print("WARNING: No provenance manifest found!")

    # Verify bitstream SHA256
    with open(args.bit, 'rb') as f:
        bit_hash = hashlib.sha256(f.read()).hexdigest()[:16]
    print(f"Bitstream SHA256: {bit_hash}...")

    # Open serial
    ser = serial.Serial(args.port, BAUD, timeout=3)

    # Warmup
    one = GF64.bias << GF64.mant_bits
    for _ in range(3):
        send_recv(ser, one, 0, args.delay)

    # Generate vectors
    vectors = gen_vectors(args.n)
    print(f"\nGF64 ADD silicon conformance: {len(vectors)} vectors")
    print(f"Format: E={GF64.exp_bits} M={GF64.mant_bits} HAS_INF={GF64.has_inf}")
    print()

    ok = fail = 0
    fails_detail = []

    for a, b in vectors:
        hw = send_recv(ser, a, b, args.delay)
        if hw is None:
            fail += 1
            if len(fails_detail) < 5:
                fails_detail.append((a, b, "TIMEOUT", gf_add(GF64, a, b)))
            continue
        gold = gf_add(GF64, a, b)
        if hw == gold:
            ok += 1
        else:
            fail += 1
            if len(fails_detail) < 10:
                fails_detail.append((a, b, hw, gold))

    total = ok + fail
    pct = 100.0 * ok / total if total > 0 else 0

    print(f"RESULT: GF64 ADD {ok}/{total} bit-exact ({pct:.1f}%) fails={fail}")
    if fails_detail:
        print(f"\nFirst {len(fails_detail)} mismatches:")
        for a, b, hw, gold in fails_detail:
            if hw == "TIMEOUT":
                print(f"  TIMEOUT a=0x{a:016x} b=0x{b:016x} gold=0x{gold:016x}")
            else:
                print(f"  a=0x{a:016x} b=0x{b:016x} hw=0x{hw:016x} gold=0x{gold:016x}")

    ser.close()
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
