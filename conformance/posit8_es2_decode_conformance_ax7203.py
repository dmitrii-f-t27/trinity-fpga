#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""posit8_es2_decode_conformance_ax7203.py — Posit8 (n=8, es=2) decode on AX7203.

Why this file did not exist
---------------------------
`conformance/` holds posit16, posit32 and posit64 decode hosts and no posit8 one. The
existing posit8 Tier-E proof in issue #199 reports its UART result without naming the
script that produced it, so pass 179 found the last Tier-E link blocked not by the board
but by a missing host.

It also matters which posit8. The board cell that proof used implements **es = 0**; the
catalogue's posit8 pack declares **es = 2**, Posit Standard 2022. They disagree on 252 of
255 values. This host drives `corona_decode_posit8_es2_ax7203`, whose bitstream is
CI run 30764181024, SHA-256
f305dc65d3edc8b827fefd0adde1bb5e9818f7d65cd32f34bd74dc17d2c7143c.

The golden model is borrowed, not rewritten
-------------------------------------------
At a fixed es, posit codes are prefix-coded: an n-bit posit is the wider one with zero
bits appended. Measured against SoftPosit, not assumed --

    posit8(es=2)[c] == posit16(es=2)[c << 8]    for all 256 codes, 0 differ

so this imports `golden_posit16` from the posit16 host and shifts. Writing a second
posit8 golden would be a second implementation of the same arithmetic, and a second
implementation is exactly how the RTL cores drifted apart in the first place: the es=0
core and the pack describe different formats because each was written separately.

    python3 conformance/posit8_es2_decode_conformance_ax7203.py --self-test
    python3 conformance/posit8_es2_decode_conformance_ax7203.py --port /dev/cu.usbserial-1120
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

FRAME = bytes([0xAA, 0x55])

# The cell captures this byte into fmt_r and never reads it -- checked in
# corona_decode_posit8_es2_ax7203.v, where fmt_r appears only in its declaration, its
# reset and its assignment. So any value works, and no FMT_POSIT8 constant is invented
# here to imply otherwise. 0x14 sits below FMT_POSIT16 = 0x15 in the existing numbering
# and is used only to keep the frame the same length.
FMT_BYTE = 0x14

# Authoritative vectors from t27's posit8_conformance_v0.json, which
# research/crossval_softposit.py verified against SoftPosit on all 255 comparable codes.
T27_VECTORS = {
    0x00: 0x00000000,   # 0.0
    0x40: 0x3F800000,   # 1.0
    0xC0: 0xBF800000,   # -1.0
    0x7F: 0x4B800000,   # maxpos, 2^24 = 16777216.0
    0x01: 0x33800000,   # minpos, 2^-24
}


def _load_posit16_golden():
    """The verified posit16 golden, imported rather than reimplemented."""
    path = os.path.join(HERE, "posit16_decode_conformance_ax7203.py")
    if not os.path.exists(path):
        return None
    # The posit16 host imports `serial` at module level even though its golden needs
    # no serial port, so loading it for the golden alone fails on a machine without
    # pyserial -- including CI. A checking function that cannot run without a board
    # driver is checking the wrong thing, so a stub stands in when the real module is
    # absent. Nothing here opens a port; run_hw imports the real pyserial itself and
    # exits 2 with the install command if it is missing.
    if "serial" not in sys.modules:
        try:
            import serial  # noqa: F401
        except ImportError:
            import types
            stub = types.ModuleType("serial")
            def _refuse(*_a, **_k):
                raise RuntimeError("pyserial is not installed; this stub exists only "
                                   "so the golden model can be loaded without it")
            stub.Serial = _refuse
            sys.modules["serial"] = stub

    spec = importlib.util.spec_from_file_location("p16_host", path)
    mod = importlib.util.module_from_spec(spec)
    # Registered before executing: a module using @dataclass looks itself up in
    # sys.modules while the decorator runs. See research/audit_module_loaders.py, where
    # an unregistered loader silently hid an oracle for eight checks.
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as e:                       # a serial import, most likely
        print(f"could not load the posit16 golden: {type(e).__name__}: {e}")
        sys.modules.pop(spec.name, None)
        return None
    return getattr(mod, "golden_posit16", None)


def golden_posit8_es2(code: int, g16) -> int:
    """FP32 bit pattern for an 8-bit posit(es=2) code."""
    return g16((code & 0xFF) << 8)


def hw_exchange(ser, code: int):
    pkt = FRAME + bytes([FMT_BYTE, code & 0xFF, 0x00, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return struct.unpack("<I", resp[1:5])[0]


def self_test() -> int:
    g16 = _load_posit16_golden()
    if g16 is None:
        print("posit16 golden unavailable; this host cannot check itself.")
        print("  it needs conformance/posit16_decode_conformance_ax7203.py, which "
              "imports pyserial")
        print("  install with : python3 -m pip install pyserial")
        return 2

    bad = 0
    for code, want in sorted(T27_VECTORS.items()):
        got = golden_posit8_es2(code, g16)
        ok = got == want
        bad += not ok
        print(f"  0x{code:02X} -> 0x{got:08X}  expected 0x{want:08X}  "
              f"{'ok' if ok else 'MISMATCH'}")
    print(f"\nself-test: golden against {len(T27_VECTORS)} t27 vectors, {bad} failures")
    print("""
The vectors come from the published posit8 pack, which crossval_softposit.py verified
against SoftPosit on all 255 comparable codes. The golden is posit16's, shifted -- so
this checks that the shift identity holds at the landmarks, not that two independent
implementations agree, because there is deliberately only one implementation.""")
    return 1 if bad else 0


def run_hw(port: str, baud: int, n: int) -> int:
    try:
        import serial
    except ImportError:
        print("pyserial is not installed; this host needs it to reach the board.")
        print("  install with : python3 -m pip install pyserial")
        return 2

    g16 = _load_posit16_golden()
    if g16 is None:
        return 2

    ser = serial.Serial(port, baud, timeout=2)
    checked = fails = 0
    # 256 codes is the whole space -- exhaustive costs nothing here, so sampling would
    # be a smaller claim for no saving.
    for code in range(256):
        hw = hw_exchange(ser, code)
        gold = golden_posit8_es2(code, g16)
        checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 10:
                shown = f"0x{hw:08X}" if hw is not None else "no response"
                print(f"MISMATCH code=0x{code:02X} hw={shown} gold=0x{gold:08X}")
    ser.close()
    print(f"HW RESULT: {checked - fails}/{checked} bit-exact (fails={fails})")
    print(f"COVERAGE: {checked} codes, exhaustive over the posit8 code space")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=256,
                    help="ignored; the code space is 256 and is always swept whole")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    return run_hw(a.port, a.baud, a.n)


if __name__ == "__main__":
    raise SystemExit(main())
