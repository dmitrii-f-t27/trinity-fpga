#!/usr/bin/env python3
"""compute_conformance_template.py — generalized compute-host for AX7203.
Tests ADD, MUL, DIV, SQRT, QUIRE for any format that has a compute bitstream.

Usage:
  python3 compute_conformance_template.py --port /dev/cu.usbserial-1120 --fmt gf16 --op add
  python3 compute_conformance_template.py --port /dev/cu.usbserial-1120 --fmt gf8 --op mul
  python3 compute_conformance_template.py --port /dev/cu.usbserial-1120 --fmt gf16 --op div
  python3 compute_conformance_template.py --port /dev/cu.usbserial-1120 --fmt gf16 --op sqrt
  python3 compute_conformance_template.py --port /dev/cu.usbserial-1120 --fmt gf16 --op quire

Supports: gf4, gf6, gf8, gf10, gf12, gf14, gf16, gf20, gf24, gf32, bf16
Operations: add, mul, div, sqrt, quire

GOLDEN
------
The default golden is the exact-Fraction oracle (conformance/gf_ref.py,
conformance/bf16_ref.py, div and sqrt via conformance/exact_ops.py).

It used to be `golden_fp32` below, which decodes each operand into a Python
float32, computes there, and encodes back. Pass 232 replaced it as the default
because that path:

  * rounds twice -- once into fp32, once into the target format
  * CLAMPS the exponent to fp32's range. gf32 has E=12, bias=2047, so most of
    its exponent range cannot exist in an fp32 at all and silently saturates
  * returns NEGATIVE infinity for x/0 for every x, including 0/0 (NaN) and
    x>0 (+Inf)
  * returns 0 for sqrt of a negative, not NaN
  * encodes every NaN as +0, and can never emit a subnormal result
  * computes `quire` as the identity -- the comment says "just return a"

`--golden fp32-proxy` still selects the old path, and `--compare` runs both over
the sample WITHOUT a board and reports where they differ, so the effect on any
past hardware run can be measured offline.

Every Tier-E compute PASS recorded before pass 232 was scored against the proxy.
Those runs need repeating against the oracle before they mean what they claim.
"""
import argparse, sys, struct, random, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Format definitions: (total_bits, exponent_bits, mantissa_bits, bias)
#
# The header used to name FIVE fields for a FOUR-field tuple -- "nbytes" was listed
# second, where the exponent width actually sits, and the unpacking below has always
# read four. Two rows were wrong against both conformance/gf_ref.py and the RTL, which
# agree with each other:
#
#   gf4  was (4, 2, 2, 1). 1+E+M = 5 for a 4-bit format, and sign_bit = 3 while the
#        exponent field works out to [3:2] -- it overlapped the sign bit. gf_ref and
#        gf_adder_param #(.EXP_BITS(1), .MANT_BITS(2)) both say E=1, M=2, bias=0.
#   gf24 was (24, 7, 17, 63) with a comment claiming the catalog uses E=7. 1+E+M = 25
#        for a 24-bit format, and three independent sources say E=9, M=14, bias=255:
#        gf_ref.py, gf_adder_param #(.EXP_BITS(9), .MANT_BITS(14)), and the
#        [1|9|14] bias=255 row in research/lut_comparison.md.
#
# research/audit_format_tables.py now checks 1+E+M == width and field disjointness
# across every format table in the corpus, so a row like these fails before it ships.
FORMATS = {
    "gf4":  (4,  1, 2, 0),
    "gf6":  (6,  2, 3, 1),
    "gf8":  (8,  3, 4, 3),
    "gf10": (10, 3, 6, 3),
    "gf12": (12, 4, 7, 7),
    "gf14": (14, 5, 8, 15),
    "gf16": (16, 6, 9, 31),  # FIXED: E=6, M=9, BIAS=31 (matches gf_ref.py + RTL)
    "gf20": (20, 7, 12, 63),
    "gf24": (24, 9, 14, 255),
    "gf32": (32, 12, 19, 2047),  # Note: gf32 in catalog uses E=12
    "bf16": (16, 8, 7, 127),
}

FRAME = bytes([0xAA, 0x55])

def golden_fp32(a_bits, b_bits, fmt_name, op):
    """Compute golden result using Python struct fp32 arithmetic."""
    total, E, M, BIAS = FORMATS[fmt_name]
    sign_bit = total - 1
    exp_lo = M
    exp_hi = M + E - 1
    e_max = (1 << E) - 1

    def to_fp32(val):
        s = (val >> sign_bit) & 1
        exp = (val >> exp_lo) & ((1 << E) - 1)
        mant = val & ((1 << M) - 1) if M > 0 else 0
        if exp == 0 and mant == 0:
            return struct.unpack('<f', struct.pack('<I', s << 31))[0]
        if exp == e_max:
            if mant == 0:
                return float('inf') * (-1 if s else 1)
            return float('nan')
        if exp == 0:
            # subnormal
            de = 1 - BIAS + 127
            if M > 0:
                mant_norm = 0
                m = mant
                while m > 0 and m < (1 << (M-1)):
                    m <<= 1
                    de -= 1
                fp32_exp = max(0, min(254, de + 127))
                fp32_mant = (m & ((1 << min(M,23)) - 1)) << max(0, 23 - M)
            else:
                fp32_exp = max(0, de)
                fp32_mant = 0
        else:
            de = exp - BIAS + 127
            fp32_exp = max(0, min(254, de))
            fp32_mant = (mant << max(0, 23 - M)) if M > 0 else 0
        fp32_bits = (s << 31) | (fp32_exp << 23) | (fp32_mant & 0x7FFFFF)
        return struct.unpack('<f', struct.pack('<I', fp32_bits))[0]

    def from_fp32(f):
        if f != f:
            return 0  # NaN -> 0 for simplicity
        if f == 0.0:
            return 0
        bits = struct.unpack('<I', struct.pack('<f', f))[0]
        s = (bits >> 31) & 1
        exp32 = (bits >> 23) & 0xFF
        mant32 = bits & 0x7FFFFF
        if exp32 == 255:
            if mant32 == 0:
                return (s << sign_bit) | (e_max << exp_lo)
            return 0
        tgt_exp = exp32 - 127 + BIAS
        if tgt_exp >= e_max:
            return (s << sign_bit) | (e_max << exp_lo)
        if tgt_exp <= 0:
            return (s << sign_bit)
        mant_out = (mant32 >> max(0, 23 - M)) & ((1 << M) - 1) if M > 0 else 0
        return (s << sign_bit) | ((tgt_exp & ((1 << E) - 1)) << exp_lo) | mant_out

    a = to_fp32(a_bits)
    b = to_fp32(b_bits)
    if op == "add":
        result = a + b
    elif op == "mul":
        result = a * b
    elif op == "div":
        if b == 0.0:
            return (1 << sign_bit) | (e_max << exp_lo)  # Inf
        result = a / b
    elif op == "sqrt":
        import math
        if a < 0:
            return 0  # NaN -> 0
        result = math.sqrt(a)
    elif op == "quire":
        # Quire: accumulate a into running sum, b selects op (0=add)
        # For golden: just return a (single accumulate test)
        result = a
    else:
        raise ValueError(f"Unknown op: {op}")
    return from_fp32(result)


def golden_oracle(a_bits, b_bits, fmt_name, op):
    """Exact-Fraction golden: the same oracles the conformance packs are built on."""
    import gf_ref, bf16_ref, exact_ops
    if fmt_name == "bf16":
        mod, fmt = bf16_ref, bf16_ref.FORMATS["bfloat16"]
    else:
        mod, fmt = gf_ref, gf_ref.FORMATS[fmt_name]
    total = FORMATS[fmt_name][0]
    mask = (1 << total) - 1
    if op == "add":
        fn = getattr(mod, "gf_add", None) or mod.format_add
    elif op == "mul":
        fn = getattr(mod, "gf_mul", None) or mod.format_mul
    elif op == "div":
        fn = exact_ops.make_div(mod)
    elif op == "sqrt":
        fn = exact_ops.make_sqrt(mod)
    elif op == "quire":
        # The RTL QUIRE core accumulates; the only golden anyone has ever run
        # against it is the identity. Hold it to that and say so, rather than
        # invent an accumulator semantics the core was never specified against.
        return mod.encode(fmt, mod.decode(fmt, a_bits & mask)) & mask
    else:
        raise ValueError("Unknown op: %s" % op)
    return fn(fmt, a_bits & mask, b_bits & mask) & mask


GOLDENS = {"oracle": golden_oracle, "fp32-proxy": golden_fp32}


def sample_pairs(fmt_name, n):
    """The exact sample run_hw uses -- shared so --compare scores the same inputs."""
    total = FORMATS[fmt_name][0]
    T = 1 << total
    rnd = random.Random(42)
    corners = [0, 1, T - 1, 1 << (total - 1), T // 2, T // 4]
    sample = corners + [rnd.randint(0, T - 1) for _ in range(max(0, n - len(corners)))]
    for a in sample:
        for b in sample[:min(8, len(sample))]:
            yield a, b


def compare_goldens(fmt_name, op, n):
    """Offline: how far apart are the two goldens on the inputs the board sees?"""
    diff = total = crashed = 0
    shown = 0
    for a, b in sample_pairs(fmt_name, n):
        total += 1
        try:
            g_o = golden_oracle(a, b, fmt_name, op)
        except Exception as e:                       # noqa: BLE001
            g_o = "raised %s" % type(e).__name__
        try:
            g_p = golden_fp32(a, b, fmt_name, op)
        except Exception as e:                       # noqa: BLE001
            # The proxy has no overflow guard: a product that exceeds fp32's
            # range reaches struct.pack('<f', ...) and raises. On a real run
            # this aborts the whole sweep for that (format, op).
            crashed += 1
            g_p = "raised %s" % type(e).__name__
        if g_o != g_p:
            diff += 1
            if shown < 5:
                print("  a=%#x b=%#x  oracle=%s  fp32-proxy=%s" % (a, b, g_o, g_p))
                shown += 1
    pct = 100.0 * diff / total if total else 0.0
    print("%-6s %-6s  oracle vs fp32-proxy: %d/%d differ (%.1f%%)%s"
          % (fmt_name, op, diff, total, pct,
             ("  proxy CRASHED on %d" % crashed) if crashed else ""))
    return diff, total, crashed


def hw_exchange(ser, a, b, nbytes):
    """Send a,b to FPGA and read back result."""
    pkt = bytearray(FRAME)
    for i in range(nbytes):
        pkt += bytes([(a >> (8*i)) & 0xFF])
    for i in range(nbytes):
        pkt += bytes([(b >> (8*i)) & 0xFF])
    pkt += bytes([0x00])  # trigger
    ser.write(pkt)
    resp_size = nbytes + 1  # A5 + nbytes data
    resp = ser.read(resp_size)
    if len(resp) < 1 or resp[0] != 0xA5:
        return None
    result = 0
    for i in range(1, min(nbytes+1, len(resp))):
        result |= resp[i] << (8*(i-1))
    return result


def run_hw(port, baud, fmt_name, op, n, golden="oracle"):
    import serial
    total, E, M, BIAS = FORMATS[fmt_name]
    nbytes = max(1, (total + 7) // 8)
    gold_fn = GOLDENS[golden]
    ser = serial.Serial(port, baud, timeout=3)
    fails = 0; checked = 0
    print(f"golden: {golden}")
    for a, b in sample_pairs(fmt_name, n):
        hw = hw_exchange(ser, a, b, nbytes)
        gold = gold_fn(a, b, fmt_name, op)
        checked += 1
        if hw is None or hw != gold:
            fails += 1
            if fails <= 5:
                print(f"MISMATCH a=0x{a:0{nbytes*2}x} b=0x{b:0{nbytes*2}x} hw={hw} gold=0x{gold:0{nbytes*2}x}")
    ser.close()
    print(f"HW RESULT: {checked - fails}/{checked} bit-exact (fails={fails}) golden={golden}")
    return fails == 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generalized compute conformance for AX7203")
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--fmt", required=True, choices=list(FORMATS.keys()))
    ap.add_argument("--op", required=True, choices=["add", "mul", "div", "sqrt", "quire"])
    ap.add_argument("--n", type=int, default=64)
    ap.add_argument("--golden", choices=sorted(GOLDENS), default="oracle",
                    help="which reference to score the board against "
                         "(default: oracle -- exact Fraction)")
    ap.add_argument("--compare", action="store_true",
                    help="no board: report where the two goldens disagree")
    args = ap.parse_args()
    if args.compare:
        diff, _, _ = compare_goldens(args.fmt, args.op, args.n)
        sys.exit(0 if diff == 0 else 1)
    sys.exit(0 if run_hw(args.port, args.baud, args.fmt, args.op, args.n,
                         args.golden) else 1)
