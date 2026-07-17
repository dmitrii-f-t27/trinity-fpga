#!/usr/bin/env python3
"""
run_silicon_conformance.py — One-shot silicon conformance for AX7203.

Designed for Linux (where FTDI serial works out of the box).
Tests GF16 ADD on physical FPGA silicon.

Usage:
  # 1. Flash bitstream (Linux, no daemon needed):
  openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
    -c "adapter speed 100" -c "init" \
    -c "pld load 0 fpga/openxc7-synth/corona_compute_gf16_add_ax7203.bit" \
    -c "runtest 200000" -c "shutdown"

  # 2. Run conformance:
  python3 conformance/run_silicon_conformance.py --port /dev/ttyUSB1 --baud 160000

  # 3. Or run ALL formats:
  python3 conformance/run_silicon_conformance.py --all
"""
import serial, time, sys, os, argparse, random, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gf_ref import FORMATS, gf_add, gf_mul, decode

# Frame format: AA 55 fmt a_lo a_hi b_lo b_hi trig (8 bytes)
# Response: A5 result_lo result_hi 00 00 (5 bytes, read 4)
FRAME_SYNC = bytes([0xAA, 0x55, 0x00])  # sync + fmt=0


def hw_exchange(ser, a, b, width=16):
    """Send operand pair, receive result."""
    pkt = FRAME_SYNC + bytes([
        a & 0xFF, (a >> 8) & 0xFF,
        b & 0xFF, (b >> 8) & 0xFF,
        0x00  # trigger
    ])
    assert len(pkt) == 8, f"Frame must be 8 bytes, got {len(pkt)}"
    ser.write(pkt)
    resp = ser.read(4)
    if len(resp) >= 3 and resp[0] == 0xA5:
        return resp[1] | (resp[2] << 8)
    return None


def run_conformance(ser, fmt_name, op='add', n=512):
    """Run conformance test for one format/operation."""
    FMT = FORMATS[fmt_name]
    W = FMT.width
    golden_fn = gf_add if op == 'add' else gf_mul

    # Corner cases
    corners = [
        0x0000, 0x0001,  # zero, smallest denorm
        0x0100 >> max(0, 16 - W),  # mid-range
    ]
    if FMT.has_inf:
        corners += [FMT.pos_inf, FMT.quiet_nan]
    corners += [FMT.max_finite]

    rnd = random.Random(42)
    coverage = corners + [rnd.randint(0, (1 << W) - 1) for _ in range(max(0, n - len(corners)))]

    passes = 0
    fails = 0
    checked = 0

    for a in coverage:
        for b in coverage[:min(8, len(coverage))]:
            gold = golden_fn(FMT, a, b)
            hw = hw_exchange(ser, a, b, W)

            checked += 1
            if hw is None:
                fails += 1
                if fails <= 5:
                    print(f"  TIMEOUT a=0x{a:04x} b=0x{b:04x}")
            elif hw == gold:
                passes += 1
            else:
                fails += 1
                if fails <= 5:
                    print(f"  MISMATCH a=0x{a:04x} b=0x{b:04x} hw=0x{hw:04x} gold=0x{gold:04x}")

    pct = passes / max(checked, 1) * 100
    status = "✓ PASS" if fails == 0 else f"✗ FAIL ({fails} mismatches)"
    print(f"  {fmt_name.upper()} {op.upper()}: {passes}/{checked} bit-exact ({pct:.1f}%) {status}")
    return fails == 0


def main():
    parser = argparse.ArgumentParser(description='AX7203 silicon conformance')
    parser.add_argument('--port', default='/dev/ttyUSB1',
                        help='Serial port (default: /dev/ttyUSB1)')
    parser.add_argument('--baud', type=int, default=160000,
                        help='Baud rate (default: 160000)')
    parser.add_argument('--all', action='store_true',
                        help='Test all available formats')
    parser.add_argument('--format', default='gf16',
                        help='Single format to test (default: gf16)')
    parser.add_argument('--op', default='add', choices=['add', 'mul'],
                        help='Operation (default: add)')
    parser.add_argument('--n', type=int, default=512,
                        help='Number of test vectors (default: 512)')
    args = parser.parse_args()

    print(f"AX7203 Silicon Conformance")
    print(f"Port: {args.port}  Baud: {args.baud}")
    print(f"Frame: AA 55 00 a_lo a_hi b_lo b_hi 00 (8 bytes)")
    print()

    try:
        ser = serial.Serial(args.port, args.baud, timeout=2)
    except Exception as e:
        print(f"ERROR: cannot open {args.port}: {e}")
        sys.exit(1)

    # Flush
    ser.read(1024)

    # Quick connectivity test
    print("Connectivity test: GF16 ADD(1.0, 1.0) = 2.0...")
    result = hw_exchange(ser, 0x3C00, 0x3C00)
    if result is None:
        print("FAIL: no response. Check:")
        print("  1. Bitstream flashed? (DONE LED on?)")
        print("  2. Correct serial port? (/dev/ttyUSB*)")
        print("  3. Correct baud rate? (160000)")
        print("  4. Frame format? (8 bytes: AA 55 00 ... 00)")
        print("  5. Press RESET button on board?")
        ser.close()
        sys.exit(1)

    if result == 0x4000:
        print(f"  ✓ Response: 0x{result:04x} = 2.0 (CORRECT)")
    else:
        print(f"  ⚠ Response: 0x{result:04x} (expected 0x4000)")
        print("  Continuing anyway...")

    print()

    # Run tests
    all_pass = True
    if args.all:
        formats_to_test = ['gf4', 'gf6', 'gf8', 'gf12', 'gf14', 'gf16', 'gf20']
        for fmt_name in formats_to_test:
            if fmt_name in FORMATS:
                ok = run_conformance(ser, fmt_name, 'add', args.n)
                all_pass = all_pass and ok
    else:
        ok = run_conformance(ser, args.format, args.op, args.n)
        all_pass = all_pass and ok

    ser.close()

    print()
    if all_pass:
        print("★★★ ALL TESTS PASSED ★★★")
    else:
        print("Some tests failed. See output above.")
    sys.exit(0 if all_pass else 1)


if __name__ == '__main__':
    main()
