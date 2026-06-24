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

import serial

TRINITY_ANCHOR = 3.0
PACK_MAGIC = "GF16"


def phi_identity() -> float:
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    return phi ** 2 + phi ** (-2)


def load_pack(path: Path) -> dict:
    with open(path, "r") as f:
        data = json.load(f)
    if data.get("magic") != PACK_MAGIC:
        raise ValueError(f"bad pack magic: {data.get('magic')}")
    return data


def uart_exchange(port: serial.Serial, a: int, b: int, cmd: int = 0) -> Tuple[int, int]:
    frame = bytes([0xAA, 0x55]) + struct.pack("<HH", a, b) + bytes([cmd])
    port.write(frame)
    resp = port.read(4)
    if len(resp) != 4:
        raise TimeoutError("short response from FPGA")
    if resp[0] != 0xA5:
        raise ValueError(f"bad response header: 0x{resp[0]:02X}")
    result = struct.unpack("<H", resp[1:3])[0]
    status = resp[3]
    return result, status


def run(pack_path: Path, device: str, baud: int = 115200, limit: int = 0) -> int:
    assert abs(phi_identity() - TRINITY_ANCHOR) < 1e-12, "TRINITY anchor broken"
    pack = load_pack(pack_path)
    vectors: List[dict] = pack["vectors"]
    if limit:
        vectors = vectors[:limit]

    with serial.Serial(device, baud, timeout=2) as port:
        fails = 0
        for i, vec in enumerate(vectors):
            a = int(vec["a"])
            b = int(vec["b"])
            expected = int(vec["result"])
            result, status = uart_exchange(port, a, b)
            ok = (result == expected) and (status == 0)
            if not ok:
                fails += 1
                print(f"FAIL[{i}] a=0x{a:04X} b=0x{b:04X} exp=0x{expected:04X} got=0x{result:04X} status={status}")
            else:
                print(f"PASS[{i}] a=0x{a:04X} b=0x{b:04X} -> 0x{result:04X}")

    total = len(vectors)
    print(f"\nResult: {total - fails}/{total} passed")
    return 0 if fails == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="GF16 conformance harness for AX7203")
    parser.add_argument("--pack", type=Path, required=True, help="GF16 conformance JSON pack")
    parser.add_argument("--device", default="/dev/ttyUSB0", help="USB-UART device")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--limit", type=int, default=0, help="Limit number of vectors")
    args = parser.parse_args()
    return run(args.pack, args.device, args.baud, args.limit)


if __name__ == "__main__":
    sys.exit(main())
