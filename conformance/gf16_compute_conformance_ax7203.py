#!/usr/bin/env python3
# gf16_compute_conformance_ax7203.py — GF16 ADD/MUL compute-HW conformance on AX7203.
# Sends two GF16 operands via UART (8-byte frame), reads 16-bit result, compares
# against the independent gf_ref.py golden (Fraction-based, RNE rounding).
import argparse, sys, struct
sys.path.insert(0, "conformance")
from gf_ref import GFFormat, FORMATS, decode, encode, Special, pow2

FMT = FORMATS["gf16"]  # exp=6, mant=9, bias=31, has_inf=True
FRAME = bytes([0xAA, 0x55])


def golden_add(a_raw, b_raw):
    a_raw &= 0xFFFF; b_raw &= 0xFFFF
    a = decode(FMT, a_raw); b = decode(FMT, b_raw)
    if isinstance(a, Special) and a.kind == "nan": return FMT.quiet_nan
    if isinstance(b, Special) and b.kind == "nan": return FMT.quiet_nan
    if isinstance(a, Special) and a.kind == "inf":
        if isinstance(b, Special) and b.kind == "inf":
            return encode(FMT, Special("inf", a.sign)) if a.sign == b.sign else FMT.quiet_nan
        return encode(FMT, Special("inf", a.sign))
    if isinstance(b, Special) and b.kind == "inf":
        return encode(FMT, Special("inf", b.sign))
    r = a + b
    if r == 0:
        sa = (a_raw >> 15) & 1; sb = (b_raw >> 15) & 1
        return (1 << 15) if (sa and sb) else 0
    return encode(FMT, r)


def golden_mul(a_raw, b_raw):
    a_raw &= 0xFFFF; b_raw &= 0xFFFF
    a = decode(FMT, a_raw); b = decode(FMT, b_raw)
    if isinstance(a, Special) and a.kind == "nan": return FMT.quiet_nan
    if isinstance(b, Special) and b.kind == "nan": return FMT.quiet_nan
    a_is_zero = not isinstance(a, Special) and a == 0
    b_is_zero = not isinstance(b, Special) and b == 0
    a_is_inf = isinstance(a, Special) and a.kind == "inf"
    b_is_inf = isinstance(b, Special) and b.kind == "inf"
    if (a_is_inf and b_is_zero) or (b_is_inf and a_is_zero): return FMT.quiet_nan
    if a_is_inf or b_is_inf:
        sg = ((a_raw >> 15) & 1) ^ ((b_raw >> 15) & 1)
        return encode(FMT, Special("inf", sg))
    if a_is_zero or b_is_zero:
        sg = ((a_raw >> 15) & 1) ^ ((b_raw >> 15) & 1)
        return (sg << 15)
    r = a * b
    return encode(FMT, r)


def hw_exchange(ser, a, b, fmt_byte=0x31):
    pkt = FRAME + bytes([fmt_byte, a & 0xFF, (a >> 8) & 0xFF, b & 0xFF, (b >> 8) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5: return None
    return resp[1] | (resp[2] << 8)


def self_test():
    # GF16: exp=6, mant=9, bias=31. 1.0=0x3E00, 2.0=0x4000, Inf=0x7E00, qNaN=0x7E01
    checks = [
        ("add", 0x3E00, 0x3E00, 0x4000),  # 1.0 + 1.0 = 2.0
        ("add", 0x3E00, 0xBE00, 0x0000),  # 1.0 + (-1.0) = +0
        ("add", 0x7E00, 0x7E00, 0x7E00),  # Inf + Inf = Inf
        ("add", 0x7E00, 0xFE00, 0x7E01),  # Inf + (-Inf) = NaN
        ("add", 0x7E01, 0x3E00, 0x7E01),  # NaN + 1.0 = NaN
        ("add", 0x0000, 0x0000, 0x0000),  # 0 + 0 = +0
        ("add", 0x8000, 0x8000, 0x8000),  # -0 + -0 = -0
        ("mul", 0x3E00, 0x3E00, 0x3E00),  # 1.0 * 1.0 = 1.0
        ("mul", 0x4000, 0x4000, 0x4200),  # 2.0 * 2.0 = 4.0
        ("mul", 0x7E00, 0x0000, 0x7E01),  # Inf * 0 = NaN
        ("mul", 0x7E00, 0x3E00, 0x7E00),  # Inf * 1.0 = Inf
        ("mul", 0x7E01, 0x3E00, 0x7E01),  # NaN * 1.0 = NaN
        ("mul", 0x0000, 0x3E00, 0x0000),  # 0 * 1.0 = +0
    ]
    bad = 0
    for op, a, b, exp in checks:
        g = golden_add(a, b) if op == "add" else golden_mul(a, b)
        ok = (g == exp)
        if not ok: bad += 1
        print(f"{'ok' if ok else 'FAIL'} {op} a=0x{a:04x} b=0x{b:04x} golden=0x{g:04x}" + ("" if ok else f" exp=0x{exp:04x}"))
    print(f"self-test: {len(checks)-bad}/{len(checks)} checks pass")
    return bad == 0


def run_hw(port, baud, op, n):
    import serial, random
    ser = serial.Serial(port, baud, timeout=2)
    golden = golden_add if op == "add" else golden_mul
    fails = checked = 0
    rnd = random.Random(42)
    corners = [
        0x0000, 0x3E00, 0x4000, 0x7E00, 0x7E01, 0xFE00, 0xFE01, 0x8000,
        0x3E01, 0xBE00, 0x4200, 0x0001, 0x7DFF, 0x4700, 0x3FFF, 0xBFFF,
    ]
    pairs = [(a, b) for a in corners for b in corners]
    pairs += [(rnd.randint(0, 0xFFFF), rnd.randint(0, 0xFFFF)) for _ in range(max(0, n - len(pairs)))]
    for a, b in pairs:
        hw = hw_exchange(ser, a, b)
        gold = golden(a, b)
        checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 15:
                print(f"MISMATCH a=0x{a:04x} b=0x{b:04x} hw=0x{hw if hw is not None else 0:04x} gold=0x{gold:04x}")
    ser.close()
    print(f"HW RESULT ({op}): {checked-fails}/{checked} bit-exact (fails={fails})")
    return fails == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--op", choices=["add", "mul"], required=True)
    ap.add_argument("--n", type=int, default=256)
    a = ap.parse_args()
    if a.self_test: sys.exit(0 if self_test() else 1)
    sys.exit(0 if run_hw(a.port, a.baud, a.op, a.n) else 1)


if __name__ == "__main__":
    main()
