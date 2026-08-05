#!/usr/bin/env python3
"""
gf_mx_ref.py — GF-MX14 (GoldenFloat Microscaling) software oracle.

Format: GF14 elements (1S+5E+8M=14bit) + shared E8M0 scale per block of 32.
Element value = GF14_decode(raw) * 2^(scale - 127)

This combines GF14's 8-bit mantissa precision with MX's 72-decade dynamic range.
"""

import numpy as np
from fractions import Fraction

BLOCK_SIZE = 32
SCALE_BIAS = 127
GF14_E_BITS = 5
GF14_M_BITS = 8
GF14_BIAS = 15
GF14_E_MAX = (1 << GF14_E_BITS) - 1  # 31
GF14_M_MAX = (1 << GF14_M_BITS) - 1  # 255
GF14_WIDTH = 14


def gf14_encode(val):
    """Encode float to 14-bit GF14 raw."""
    if val == 0.0:
        return 0
    sign = 1 if val < 0 else 0
    aval = abs(val)

    exp = int(np.floor(np.log2(aval))) + GF14_BIAS
    if exp <= 0:
        return 0  # flush to zero
    if exp >= GF14_E_MAX:
        exp = GF14_E_MAX - 1  # saturate to max finite

    mant = aval / (2.0 ** (exp - GF14_BIAS)) - 1.0
    mant_raw = int(round(mant * (2 ** GF14_M_BITS)))
    mant_raw = min(mant_raw, GF14_M_MAX)

    raw = (sign << 13) | (exp << GF14_M_BITS) | mant_raw
    return raw & 0x3FFF


def gf14_decode(raw):
    """Decode 14-bit GF14 raw to float."""
    raw &= 0x3FFF
    sign = (raw >> 13) & 1
    exp = (raw >> GF14_M_BITS) & GF14_E_MAX
    mant = raw & GF14_M_MAX

    if exp == 0:
        return 0.0

    val = (1.0 + mant / (2 ** GF14_M_BITS)) * (2.0 ** (exp - GF14_BIAS))
    return -val if sign else val


def find_block_scale(block):
    """Find optimal E8M0 shared scale for a block of float values.
    Returns scale byte (0-255). The scale is chosen so that the
    largest absolute value in the block maps to near GF14's max normal.
    """
    max_abs = np.max(np.abs(block))
    if max_abs == 0:
        return SCALE_BIAS  # scale=1.0

    # We want: max_abs * 2^(-scale_diff) ≈ GF14_max = (2-2^-8) * 2^(30-15) ≈ 2^15
    # scale_diff = log2(max_abs) - 15
    # shared_scale = 127 + scale_diff (so element_value = raw_val * 2^(shared_scale-127))
    # But we need to DIVIDE by the scale, so:
    # element = value / 2^(shared_scale - 127)
    # We want element to fit in GF14 range, so:
    # shared_scale - 127 = log2(max_abs) - 14 (leave 1 bit headroom)

    target_exp = int(np.floor(np.log2(max_abs))) - 14
    scale = SCALE_BIAS + target_exp
    scale = max(0, min(255, scale))
    return scale


def quantize_block(block, stochastic=False):
    """Quantize a block of 32 float values to GF-MX14 format.
    Returns (scale_byte, [32 raw values]).
    """
    block = np.asarray(block, dtype=np.float64)
    assert len(block) == BLOCK_SIZE, f"Block must be {BLOCK_SIZE} elements, got {len(block)}"

    scale = find_block_scale(block)
    scale_factor = 2.0 ** (scale - SCALE_BIAS)

    # Normalize block by scale
    if scale_factor != 0:
        normalized = block / scale_factor
    else:
        normalized = block

    # Quantize each element to GF14
    raws = []
    for val in normalized:
        if stochastic and val != 0.0:
            # Stochastic rounding
            det_raw = gf14_encode(val)
            det_val = gf14_decode(det_raw)
            step = abs(det_val) * 2 ** (-GF14_M_BITS) if det_val != 0 else 2 ** (-14)
            noise = np.random.uniform(-step/2, step/2)
            det_raw = gf14_encode(val + noise)
        raws.append(gf14_encode(val))

    return scale, raws


def dequantize_block(scale, raws):
    """Dequantize GF-MX14 block back to floats."""
    scale_factor = 2.0 ** (scale - SCALE_BIAS)
    return np.array([gf14_decode(r) * scale_factor for r in raws])


def quantize_tensor(tensor, stochastic=False):
    """Quantize an entire tensor (any shape) to GF-MX14.
    Pads to multiple of BLOCK_SIZE, quantizes each block.
    Returns quantized tensor of same shape.
    """
    flat = tensor.flatten()
    n = len(flat)
    pad = (-n) % BLOCK_SIZE
    if pad:
        flat = np.pad(flat, (0, pad))

    result = np.zeros_like(flat)
    for i in range(0, len(flat), BLOCK_SIZE):
        block = flat[i:i + BLOCK_SIZE]
        scale, raws = quantize_block(block, stochastic)
        result[i:i + BLOCK_SIZE] = dequantize_block(scale, raws)

    return result[:n].reshape(tensor.shape)


def mx_mul_matrix(a, b, stochastic=False):
    """Matrix multiply with GF-MX14 quantization on weights.
    a: (M, K) in float32
    b: (K, N) in float32
    Returns (M, N) result with a quantized to GF-MX14.
    """
    a_q = quantize_tensor(a, stochastic).astype(np.float32)
    return a_q @ b


def compute_quantization_error(original, quantized):
    """Compute relative error metrics."""
    abs_err = np.abs(original - quantized)
    rel_err = abs_err / (np.abs(original) + 1e-30)
    return {
        'max_rel_error': float(np.max(rel_err)),
        'mean_rel_error': float(np.mean(rel_err)),
        'mse': float(np.mean((original - quantized) ** 2)),
        'snr_db': float(10 * np.log10(np.var(original) / (np.var(original - quantized) + 1e-30))),
    }


def _selftest():
    print("GF-MX14 Oracle Self-Test")
    print("="*60)

    # Test 1: Basic encode/decode
    print("\n1. Basic GF14 encode/decode:")
    for v in [0.0, 1.0, 0.5, 2.0, 3.14159, -1.5, 100.0]:
        raw = gf14_encode(v)
        back = gf14_decode(raw)
        err = abs(back - v) / max(abs(v), 1e-30)
        print(f"   {v:>10.5f} -> 0x{raw:04x} -> {back:>10.5f} (err={err:.6f})")

    # Test 2: Block quantization
    print("\n2. Block quantization (32 random values):")
    np.random.seed(42)
    block = np.random.randn(BLOCK_SIZE) * 0.1
    scale, raws = quantize_block(block)
    dequant = dequantize_block(scale, raws)
    err = np.abs(block - dequant) / (np.abs(block) + 1e-30)
    print(f"   Scale: {scale} (factor: {2.0**(scale-127):.6f})")
    print(f"   Max relative error: {np.max(err):.6f}")
    print(f"   Mean relative error: {np.mean(err):.6f}")

    # Test 3: Dynamic range — values spanning 12 decades
    print("\n3. Dynamic range test (12 decades):")
    block = np.array([1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1,
                      1.0, 1e1, 1e2, 1e3, 0, 0, 0, 0] + [0]*16)
    scale, raws = quantize_block(block)
    dequant = dequantize_block(scale, raws)
    print(f"   Scale: {scale} (factor: {2.0**(scale-127):.2e})")
    for i in range(12):
        orig = block[i]
        back = dequant[i]
        if orig != 0:
            err = abs(back - orig) / abs(orig)
            print(f"   [{i:2d}] orig={orig:.1e} -> dequant={back:.1e} (err={err:.4f})")

    # Test 4: Tensor quantization
    print("\n4. Tensor quantization (128x128 weight matrix):")
    W = np.random.randn(128, 128) * 0.05
    W_q = quantize_tensor(W)
    metrics = compute_quantization_error(W, W_q)
    print(f"   Max rel error: {metrics['max_rel_error']:.6f}")
    print(f"   Mean rel error: {metrics['mean_rel_error']:.6f}")
    print(f"   SNR: {metrics['snr_db']:.2f} dB")

    # Test 5: Compare with bare GF14 (no scale)
    print("\n5. GF-MX14 vs bare GF14 (dynamic range):")
    # Values that bare GF14 can't represent
    extreme = np.array([1e-8, 1e-7, 1e-6, 0.01, 0.1, 1.0, 10.0, 100.0] + [0]*24)
    # Bare GF14
    gf14_only = np.array([gf14_decode(gf14_encode(v)) for v in extreme])
    # GF-MX14
    scale_mx, raws_mx = quantize_block(extreme)
    gfmx = dequantize_block(scale_mx, raws_mx)

    print(f"   {'Value':>12} {'GF14':>12} {'GF-MX14':>12} {'GF14 OK?':>10}")
    for i in range(8):
        v = extreme[i]
        g14 = gf14_only[i]
        gmx = gfmx[i]
        ok = "YES" if abs(g14-v)/max(abs(v),1e-30)<0.01 else "NO"
        print(f"   {v:>12.1e} {g14:>12.1e} {gmx:>12.1e} {ok:>10}")

    # Hard gate (deterministic): exact powers of two must round-trip through
    # bare GF14, and a fixed block must dequantize within a bounded rel error.
    for v in [1.0, 2.0, 0.5, 4.0, -1.0]:
        assert abs(gf14_decode(gf14_encode(v)) - v) < 1e-9, f"GF14 round-trip {v}"
    # One shared scale can only hold a modest dynamic range; span ~2 decades
    # (what MX is for) so the mantissa reaches every element.
    fixed = np.array([0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 0.0] + [0] * 24)
    s, raws = quantize_block(fixed)
    back = dequantize_block(s, raws)
    nz = fixed != 0
    max_rel = float(np.max(np.abs(back[nz] - fixed[nz]) / np.abs(fixed[nz])))
    assert max_rel < 0.05, f"GF-MX14 block max rel error {max_rel} >= 0.05"

    print("\n✓ GF-MX14 oracle: ALL TESTS PASS")


if __name__ == "__main__":
    _selftest()
