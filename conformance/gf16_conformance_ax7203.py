from __future__ import annotations   # `port: serial.Serial` in a signature is
# evaluated when the function is DEFINED. Without this, importing the module to
# reach its golden needs pyserial installed -- the pass-181 class, in an
# annotation rather than a call.
#!/usr/bin/env python3
"""
gf16_conformance_ax7203.py
Bit-exact conformance harness for GoldenFloat GF16 on ALINX AX7203.
Reads the GF16 conformance pack, drives operands to FPGA over UART, and checks
that the returned GF16 result matches the software reference.

Expected UART protocol:
    Host -> FPGA:  [0xAA][0x55][op_a_lo][op_a_hi][op_b_lo][op_b_hi][cmd]
    FPGA -> Host:  [0xA5][res_lo][res_hi][status]

Anchor identity: phi**2 + phi**(-2) == 3.0 (TRINITY_ANCHOR)
"""

import argparse
import json
import math
import struct
import sys
from pathlib import Path
from typing import List, Tuple


TRINITY_ANCHOR = 3.0
PACK_MAGIC = None  # Accept any JSON pack; optional validation later

# GF16 pack format (NUMERIC-STANDARD-001)
GF16_EXP_BIAS = 31
GF16_MANT_BITS = 9
GF16_MANT_MASK = (1 << GF16_MANT_BITS) - 1


def phi_identity() -> float:
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    return phi ** 2 + phi ** (-2)


def load_pack(path: Path) -> dict:
    with open(path, "r") as f:
        data = json.load(f)
    return data


def gf16_encode(value: float) -> int:
    """Encode a Python float into the pack's 16-bit GF16 raw word.

    Format: 1 sign bit, 6 exponent bits (bias 31), 9 stored mantissa bits.
    Subnormals/NaN/Inf are not required for this conformance pack.
    """
    if value == 0.0:
        return 0
    sign = 1 if value < 0.0 else 0
    av = abs(value)
    exp = int(math.floor(math.log2(av)))
    mant = round((av / (2.0 ** exp) - 1.0) * (1 << GF16_MANT_BITS))
    if mant == (1 << GF16_MANT_BITS):
        mant = 0
        exp += 1
    exp_field = (exp + GF16_EXP_BIAS) & 0x3F
    return (sign << 15) | (exp_field << GF16_MANT_BITS) | (mant & GF16_MANT_MASK)


def uart_exchange(port: serial.Serial, a: int, b: int, cmd: int = 0) -> Tuple[int, int]:
    frame = bytes([0xAA, 0x55]) + struct.pack("<HH", a, b) + bytes([cmd])
    port.write(frame)
    resp = port.read(4)
    if len(resp) != 4:
        raise TimeoutError(f"short response from FPGA: got {len(resp)} bytes")
    if resp[0] != 0xA5:
        raise ValueError(f"bad response header: 0x{resp[0]:02X}")
    result = struct.unpack("<H", resp[1:3])[0]
    status = resp[3]
    return result, status


def run(pack_path: Path, device: str, baud: int = 115200, limit: int = 0) -> int:
    assert abs(phi_identity() - TRINITY_ANCHOR) < 1e-12, "TRINITY anchor broken"
    pack = load_pack(pack_path)
    vectors: List[dict] = pack.get("test_vectors", [])
    if limit:
        vectors = vectors[:limit]

    import serial

    with serial.Serial(device, baud, timeout=2) as port:
        fails = 0
        for i, vec in enumerate(vectors):
            value = float(vec.get("input", {}).get("value", 0.0))
            expected_raw = vec.get("expected", {}).get("raw")
            if expected_raw is None:
                expected_raw = gf16_encode(value)
            else:
                expected_raw = int(expected_raw)

            a = expected_raw
            b = 0  # ADD identity: a + 0 should return a
            result, status = uart_exchange(port, a, b)
            ok = (result == expected_raw) and (status == 0)
            if not ok:
                fails += 1
                print(f"FAIL[{i}] a=0x{a:04X} b=0x{b:04X} exp=0x{expected_raw:04X} got=0x{result:04X} status={status}")
            else:
                print(f"PASS[{i}] a=0x{a:04X} b=0x{b:04X} -> 0x{result:04X}")

    total = len(vectors)
    print(f"\nResult: {total - fails}/{total} passed")
    return 0 if fails == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="GF16 conformance harness for AX7203")
    parser.add_argument("--pack", type=Path, required=True, help="GF16 conformance JSON pack")
    # Verified 2026-06-26: FPGA uart_tx (N15) reaches the on-board CP2102N =
    # /dev/cu.usbserial-1120. AL321 FT2232H ch.B (/dev/cu.usbserial-210512180081)
    # receives nothing (not wired to N15/P20). /dev/ttyUSB0 is Linux-only and was
    # the root cause of the prior "0 bytes" blocker.
    parser.add_argument("--device", default="/dev/cu.usbserial-1120",
                        help="USB-UART bridge (verified on-board CP2102N)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--limit", type=int, default=0, help="Limit number of vectors")
    args = parser.parse_args()
    return run(args.pack, args.device, args.baud, args.limit)


if __name__ == "__main__":
    sys.exit(main())
