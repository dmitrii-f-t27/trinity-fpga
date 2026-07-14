#!/usr/bin/env python3
"""posit64 decode conformance — Posit64 (es=2) → FP32. 8-byte frame."""
import serial, struct, time, random, sys, math, argparse

def posit64_to_fp32(raw):
    """Posit64 (n=64, es=2) → FP32 bits via Python float."""
    if raw == 0: return 0x00000000
    if raw == 0x8000000000000000: return 0x7FC00000  # NaR
    sign = (raw >> 63) & 1
    abs_val = raw & 0x7FFFFFFFFFFFFFFF
    if sign: abs_val = ((~abs_val) + 1) & 0x7FFFFFFFFFFFFFFF
    regime_sign = (abs_val >> 62) & 1
    regime_bits = abs_val if not regime_sign else (~abs_val) & 0x7FFFFFFFFFFFFFFF
    # LZC on 63-bit
    lzc = 0
    for i in range(62, -1, -1):
        if (regime_bits >> i) & 1:
            lzc = 62 - i
            break
    else:
        lzc = 62
    if lzc > 61: lzc = 61
    regime_k = (lzc - 1) if regime_sign else (-lzc)
    regime_total = (lzc + 1) if lzc < 61 else lzc
    after_regime = (abs_val << regime_total) & 0x7FFFFFFFFFFFFFFF
    e_field = (after_regime >> 61) & 0x3
    frac_field = (after_regime << 2) & 0x7FFFFFFFFFFFFFFF
    exp_true = 4 * regime_k + e_field
    mant_pre = (frac_field >> 40) & 0x7FFFFF
    guard = (frac_field >> 39) & 1
    round_b = (frac_field >> 38) & 1
    sticky = 1 if (frac_field & ((1<<38)-1)) else 0
    round_up = guard and (round_b or sticky or (mant_pre & 1))
    mant_rnd = mant_pre + (1 if round_up else 0)
    mant_carry = 1 if mant_rnd > 0x7FFFFF else 0
    mant_final = mant_rnd & 0x7FFFFF
    exp_final = exp_true + 127 + (1 if mant_carry else 0)
    if exp_final > 254:
        return (sign << 31) | 0x7F800000
    elif exp_final < 1:
        return (sign << 31)
    return (sign << 31) | ((exp_final & 0xFF) << 23) | mant_final

def make_codes():
    codes = set()
    codes.add(0); codes.add(0x8000000000000000)  # zero, NaR
    # ±1 (regime=0, exp=0, frac=0)
    codes.add(0x4000000000000000)  # +1.0
    codes.add(0xC000000000000000)  # -1.0
    # Powers of useed (regime only)
    for k in range(-5, 6):
        if k >= 0:
            val = 0x4000000000000000
            for _ in range(k):
                val = (val << 1) | 1
                val = (val << 1)
            val &= 0x7FFFFFFFFFFFFFFF
            if val: codes.add(val); codes.add(val | 0x8000000000000000)
        else:
            val = 0x2000000000000000
            for _ in range(abs(k)-1):
                val >>= 2
            val &= 0x7FFFFFFFFFFFFFFF
            if val: codes.add(val); codes.add(val | 0x8000000000000000)
    rng = random.Random(64)
    for _ in range(2000):
        codes.add(rng.randrange(1 << 64))
    return sorted(codes)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', default='/dev/cu.usbserial-1120')
    ap.add_argument('--baud', type=int, default=160000)
    args = ap.parse_args()
    codes = make_codes()
    port = serial.Serial(args.port, args.baud, timeout=2)
    ok = 0; fails = []
    for raw in codes:
        golden = posit64_to_fp32(raw)
        b = [(raw >> (i*8)) & 0xFF for i in range(8)]
        port.write(bytes([0xAA, 0x55, 0x00] + b + [0x00]))
        time.sleep(0.005)
        resp = port.read(5)
        if len(resp) >= 5 and resp[0] == 0xA5:
            dut = resp[1] | (resp[2]<<8) | (resp[3]<<16) | (resp[4]<<24)
            golden_is_nan = ((golden >> 23) & 0xFF) == 0xFF and (golden & 0x7FFFFF)
            dut_is_nan = ((dut >> 23) & 0xFF) == 0xFF and (dut & 0x7FFFFF)
            if (golden_is_nan and dut_is_nan) or dut == golden: ok += 1
            else:
                if len(fails) < 10: fails.append(f"raw={raw:#018x} g={golden:#010x} d={dut:#010x}")
        else:
            if len(fails) < 10: fails.append(f"raw={raw:#018x} noresp")
    print(f"HW RESULT: {ok}/{len(codes)} bit-exact (fails={len(codes)-ok})")
    for f in fails: print(f"  {f}", file=sys.stderr)
    port.close()

if __name__ == '__main__':
    main()
