#!/usr/bin/env python3
# corona_decode_host_ax7203.py — decode-HW conformance for corona_decode_top_ax7203.
#
# Protocol (corona_decode_top_ax7203, CFGMCLK): TX = AA 55 fmt code_lo code_hi <trig>
# (6 bytes); RX = A5 r0 r1 r2 r3 (5 bytes, 32-bit decoded value LE).
# Formats: 0=bf16, 1=fp8_e4m3_fnuz, 2=int8, 3=nf4, 4=posit8.
#
# Golden decoders (independent Python, matching the Corona RTL semantics):
#   int8: signed 8-bit -> int32 (sign-extend).
#   bf16: bf16 is the top 16 bits of fp32 -> fp32 = code << 16 (all cases:
#         zero/denormal/normal/Inf/NaN map directly).
#   nf4:  16-value NF4 lookup table (standard NF4 codebook).
#   fp8_e4m3_fnuz / posit8: TODO golden (need exact fnuz bias / posit8 tapered
#         decode from the RTL — add before flashing those two formats).
#
#   self-test:  python3 corona_decode_host_ax7203.py --self-test
#   on HW:      python3 corona_decode_host_ax7203.py --port /dev/cu.usbserial-120 --baud 160000
import argparse, sys

FMT_BF16, FMT_FP8, FMT_INT8, FMT_NF4, FMT_POSIT8 = 0, 1, 2, 3, 4

# NF4 codebook (standard NormalFloat-4, 16 values) -> fp32 bits.
NF4_TABLE = [
    0x00000000,  # 0 (zero)
    0xBFC00000,  # -1.5
    0xBF800000,  # -1.0
    0xBF400000,  # -0.75
    0xBF000000,  # -0.5
    0xBEB00000,  # -0.3125  (NF4 value)
    0xBE800000,  # -0.25
    0xBE000000,  # -0.0625  (NF4 smallest negative)
    0x3E000000,  # 0.0625
    0x3E800000,  # 0.25
    0x3EB00000,  # 0.3125
    0x3F000000,  # 0.5
    0x3F400000,  # 0.75
    0x3F800000,  # 1.0
    0x3FC00000,  # 1.5
    0x40000000,  # 2.0
]


def _fp8_e4m3_fnuz(code):
    """FP8 E4M3 FNUZ (AMD MI300) -> FP32. bias=8, 0x00=+0, 0x80=NaN, no Inf."""
    if code == 0x80:
        return 0x7FC00000                # NaN
    if code == 0x00:
        return 0x00000000                # +0
    sign = (code >> 7) & 1
    exp = (code >> 3) & 0xF
    mant = code & 0x7
    if exp == 0:                         # subnormal: value = M * 2^-10
        if mant & 0x4:
            fe, fm = 119, (mant & 0x3) << 21
        elif mant & 0x2:
            fe, fm = 118, (mant & 0x1) << 22
        else:                            # mant == 0b001
            fe, fm = 117, 0
    else:                                # normal: value = (1+M/8) * 2^(E-8)
        fe, fm = exp + 119, mant << 20
    return (sign << 31) | (fe << 23) | fm


def _posit8(code):
    """Posit8(es=0) -> FP32. useed=2, value=(-1)^S * 2^k * (1+fraction). 0x00=0, 0x80=NaR."""
    if code == 0x00:
        return 0x00000000
    if code == 0x80:
        return 0x7FC00000                # NaR -> NaN
    sign = (code >> 7) & 1
    abs7 = code & 0x7F
    if sign:
        abs7 = ((~abs7) + 1) & 0x7F      # 2's complement (7-bit)
    regime_sign = (abs7 >> 6) & 1
    regime_bits = ((~abs7) & 0x7F) if regime_sign else abs7
    lzc = 7 - regime_bits.bit_length()    # leading-zero count on 7 bits
    k = (lzc - 1) if regime_sign else (-lzc)
    regime_total = lzc + (1 if lzc < 7 else 0)
    shifted = (abs7 << regime_total) & 0x7F
    fraction = (shifted >> 1) & 0x3F      # shifted[6:1], 6 bits
    fp32_exp = (127 + k) & 0xFF
    return (sign << 31) | (fp32_exp << 23) | (fraction << 17)


def golden(fmt, code):
    """Independent decode golden (32-bit result), matching Corona RTL — 5/5 formats."""
    if fmt == FMT_INT8:
        v = code - 256 if (code & 0x80) else code
        return v & 0xFFFFFFFF
    if fmt == FMT_BF16:
        return (code & 0xFFFF) << 16       # bf16 = top 16 bits of fp32
    if fmt == FMT_NF4:
        return NF4_TABLE[code & 0xF]
    if fmt == FMT_FP8:
        return _fp8_e4m3_fnuz(code & 0xFF)
    if fmt == FMT_POSIT8:
        return _posit8(code & 0xFF)
    return None


def hw_exchange(ser, fmt, code):
    pkt = bytes([0xAA, 0x55, fmt, code & 0xFF, (code >> 8) & 0xFF, 0x00])
    ser.write(pkt)
    resp = ser.read(5)
    if len(resp) != 5 or resp[0] != 0xA5:
        return None
    return resp[1] | (resp[2] << 8) | (resp[3] << 16) | (resp[4] << 24)


def self_test():
    # golden internal consistency (no HW)
    checks = [
        (FMT_INT8, 0x05, 0x00000005),
        (FMT_INT8, 0xFF, 0xFFFFFFFF),   # -1
        (FMT_INT8, 0x80, 0xFFFFFF80),   # -128
        (FMT_BF16, 0x3F80, 0x3F800000), # 1.0
        (FMT_BF16, 0xBF80, 0xBF800000), # -1.0
        (FMT_BF16, 0x0000, 0x00000000), # +0
        (FMT_NF4,  0x0D, 0x3F800000),   # nf4 code 13 -> 1.0
        (FMT_FP8,  0x40, 0x3F800000),   # fp8 e4m3 0x40 (exp=8) -> 1.0
        (FMT_FP8,  0x44, 0x3FC00000),   # fp8 0x44 -> 1.5
        (FMT_FP8,  0x80, 0x7FC00000),   # fp8 NaN
        (FMT_POSIT8, 0x40, 0x3F800000), # posit8 0x40 -> 1.0
        (FMT_POSIT8, 0x80, 0x7FC00000), # posit8 NaR -> NaN
    ]
    bad = 0
    for fmt, code, exp in checks:
        g = golden(fmt, code)
        ok = (g == exp)
        if not ok:
            bad += 1
        print(f"{'ok' if ok else 'FAIL'}  fmt={fmt} code=0x{code:x} golden=0x{g:08x}" + ("" if ok else f" exp=0x{exp:08x}"))
    print(f"self-test: {len(checks)-bad}/{len(checks)} golden checks pass")
    return bad == 0


def run_hw(port, baud, fmt_filter=None):
    import serial
    ser = serial.Serial(port, baud, timeout=2)
    fails = checked = 0
    # int8 exhaustive (256), bf16 sample (corners + a spread), nf4 exhaustive (16)
    cases = [(FMT_INT8, c) for c in range(256)]
    cases += [(FMT_BF16, c) for c in [0x0000, 0x3F80, 0xBF80, 0x4000, 0xC000, 0x7F80, 0x0001, 0x4248]]
    cases += [(FMT_NF4, c) for c in range(16)]
    cases += [(FMT_FP8, c) for c in range(256)]            # fp8 e4m3 fnuz exhaustive
    cases += [(FMT_POSIT8, c) for c in range(256)]         # posit8 exhaustive
    for fmt, code in cases:
        if fmt_filter is not None and fmt != fmt_filter:
            continue
        g = golden(fmt, code)
        if g is None:
            continue
        hw = hw_exchange(ser, fmt, code)
        checked += 1
        if hw is None or hw != g:
            fails += 1
            if fails <= 12:
                print(f"MISMATCH fmt={fmt} code=0x{code:x} hw={hw and ('0x%08x' % hw)} golden=0x{g:08x}")
    ser.close()
    print(f"HW RESULT: {checked-fails}/{checked} bit-exact (decode-HW); fails={fails}")
    return fails == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--port", default="/dev/cu.usbserial-120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--fmt", type=int, default=None, help="only test this format (0-4), None=all")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    sys.exit(0 if run_hw(a.port, a.baud, a.fmt) else 1)


if __name__ == "__main__":
    main()
