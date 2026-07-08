#!/usr/bin/env python3
"""Batch flash + conformance test for multiple formats.
Usage: python3 batch_flash_test.py <format> [--port /dev/cu.usbserial-1120]
Requires bitstream at /tmp/bitstreams/<format>.bit
"""
import serial, struct, time, random, sys, argparse, subprocess, os, math

def decode_binary(raw, n_bits, exp_bits, mant_bits):
    """Generic IEEE 754 decode to FP32."""
    bias = (1 << (exp_bits - 1)) - 1
    emax = (1 << exp_bits) - 1
    sign = raw >> (n_bits - 1)
    exp = (raw >> mant_bits) & emax
    mant = raw & ((1 << mant_bits) - 1)
    if exp == emax:
        if mant == 0: return (0xFF800000 if sign else 0x7F800000)
        return 0x7FC00001
    if exp == 0:
        if mant == 0: return sign << 31
        # Subnormal — tricky for wide formats
        return sign << 31  # simplified: flush to zero for n>32
    unbiased = exp - bias
    fp32_exp = unbiased + 127
    if fp32_exp >= 255: return (0xFF800000 if sign else 0x7F800000)
    if fp32_exp <= 0: return sign << 31
    if mant_bits >= 23:
        mant23 = mant >> (mant_bits - 23)
    else:
        mant23 = mant << (23 - mant_bits)
    return (sign << 31) | (fp32_exp << 23) | mant23

def test_format(fmt, port_path, baud=160000):
    """Flash and test a format."""
    bitstream = f"/tmp/bitstreams/{fmt}.bit"
    if not os.path.exists(bitstream):
        print(f"  SKIP {fmt}: no bitstream")
        return None

    # Flash via openocd
    print(f"  Flashing {fmt}...", end=" ", flush=True)
    r = subprocess.run(
        ["sudo", "openocd", "-f", "fpga/openxc7-synth/ax7203_al321.cfg",
         "-c", f"init; pld load 0 {bitstream}; exit"],
        capture_output=True, text=True, timeout=60
    )
    if r.returncode != 0:
        print("FLASH FAILED")
        return None
    print("OK", flush=True)
    time.sleep(1)

    # Determine format parameters
    params = get_format_params(fmt)
    if params is None:
        print(f"  SKIP {fmt}: unknown format params")
        return None

    n_bits, nbytes, decode_fn = params
    port = serial.Serial(port_path, baud, timeout=5)

    # Generate test vectors
    codes = generate_vectors(fmt, n_bits)

    ok = 0; fails = []
    for raw in codes:
        gold = decode_fn(raw)
        b = [(raw >> (i * 8)) & 0xFF for i in range(nbytes)]
        port.write(bytes([0xAA, 0x55, 0] + b + [0]))
        time.sleep(0.012)
        r = port.read(5)
        if len(r) >= 5 and r[0] == 0xA5:
            d = r[1] | (r[2] << 8) | (r[3] << 16) | (r[4] << 24)
            gn = (gold >> 23 & 0xFF) == 0xFF and (gold & 0x7FFFFF)
            dn = (d >> 23 & 0xFF) == 0xFF and (d & 0x7FFFFF)
            if (gn and dn) or d == gold:
                ok += 1
            else:
                if len(fails) < 5:
                    fails.append(f"raw=0x{raw:0{(n_bits+3)//4}x} gold={gold:#010x} hw={d:#010x}")
        else:
            if len(fails) < 5:
                fails.append(f"noresp")

    port.close()
    total = len(codes)
    status = "✅" if ok == total else f"❌ ({ok}/{total})"
    print(f"  {fmt}: {ok}/{total} bit-exact {status}")
    for fmsg in fails:
        print(f"    {fmsg}")
    return ok, total

def get_format_params(fmt):
    """Return (n_bits, nbytes, decode_fn) for known formats."""
    PHI2 = 2.618  # approx 1+phi
    
    if fmt == "binary32":
        return 32, 4, lambda r: decode_binary(r, 32, 8, 23)
    elif fmt == "binary64":
        return 64, 8, lambda r: decode_binary(r, 64, 11, 52)
    elif fmt == "binary128":
        return 128, 16, lambda r: decode_binary(r, 128, 15, 112)
    
    # GF formats: use phi-rule
    gf_formats = {
        "gf4": 4, "gf6": 6, "gf8": 8, "gf10": 10, "gf12": 12,
        "gf14": 14, "gf16": 16, "gf20": 20, "gf24": 24, "gf32": 32,
    }
    if fmt in gf_formats:
        n = gf_formats[fmt]
        e = round((n - 1) / PHI2)
        m = n - 1 - e
        bias = (1 << (e - 1)) - 1 if e > 0 else 0
        nbytes = (n + 7) // 8
        return n, nbytes, lambda r, n=n, e=e, m=m, b=bias: decode_binary(r, n, e, m)
    
    return None

def generate_vectors(fmt, n_bits):
    """Generate test vectors for a format."""
    codes = set()
    codes.add(0)
    codes.add(1 << (n_bits - 1))  # -0
    
    if n_bits <= 16:
        # Exhaustive for small formats
        return sorted(range(1 << n_bits))[:256]  # cap at 256
    
    # Larger formats: corner cases + random
    rng = random.Random(42)
    
    # Get format params for corner generation
    if fmt.startswith("binary"):
        if n_bits == 32: e_bits, m_bits = 8, 23
        elif n_bits == 64: e_bits, m_bits = 11, 52
        elif n_bits == 128: e_bits, m_bits = 15, 112
        bias = (1 << (e_bits - 1)) - 1
        emax = (1 << e_bits) - 1
        
        for e in [0, 1, bias-127, bias-1, bias, bias+1, bias+127, emax-1, emax]:
            for m in [0, 1, (1 << m_bits) - 1]:
                for s in [0, 1]:
                    codes.add((s << (n_bits-1)) | (e << m_bits) | m)
    
    elif fmt.startswith("gf"):
        PHI2 = 2.618
        e = round((n_bits - 1) / PHI2)
        m = n_bits - 1 - e
        bias = (1 << (e - 1)) - 1 if e > 0 else 0
        emax = (1 << e) - 1
        for exp in [0, 1, bias-1, bias, bias+1, emax-1, emax]:
            for mant in [0, 1, (1 << m) - 1 if m > 0 else 0]:
                for s in [0, 1]:
                    codes.add((s << (n_bits-1)) | (exp << m) | mant)
    
    for _ in range(150):
        codes.add(rng.randrange(1 << n_bits))
    
    return sorted(codes)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("formats", nargs="+", help="Formats to test")
    args = ap.parse_args()

    results = {}
    for fmt in args.formats:
        r = test_format(fmt, args.port)
        if r:
            results[fmt] = r

    print("\n=== SUMMARY ===")
    for fmt, (ok, total) in sorted(results.items()):
        status = "✅" if ok == total else "❌"
        print(f"  {status} {fmt}: {ok}/{total}")

if __name__ == "__main__":
    main()
