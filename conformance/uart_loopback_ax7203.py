#!/usr/bin/env python3
"""
uart_loopback_ax7203.py
Diagnostic harness for ALINX AX7203 UART loopback bitstream.
Sends bytes and checks that each byte is echoed back.

Expected UART protocol:
    Host -> FPGA: [any byte]
    FPGA -> Host: [same byte]
"""

import argparse
import sys
from pathlib import Path

import serial


def run(device: str, baud: int = 115200, count: int = 10) -> int:
    with serial.Serial(device, baud, timeout=2) as port:
        fails = 0
        for i in range(count):
            tx_byte = (0xAA + i) & 0xFF
            port.write(bytes([tx_byte]))
            rx = port.read(1)
            if len(rx) != 1:
                print(f"FAIL[{i}] sent 0x{tx_byte:02X}, got {len(rx)} bytes")
                fails += 1
                continue
            if rx[0] != tx_byte:
                print(f"FAIL[{i}] sent 0x{tx_byte:02X}, got 0x{rx[0]:02X}")
                fails += 1
            else:
                print(f"PASS[{i}] 0x{tx_byte:02X} -> 0x{rx[0]:02X}")

    print(f"\nResult: {count - fails}/{count} passed")
    return 0 if fails == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="UART loopback diagnostic for AX7203")
    parser.add_argument("--device", default="/dev/ttyUSB0", help="USB-UART device")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    return run(args.device, args.baud, args.count)


if __name__ == "__main__":
    sys.exit(main())
