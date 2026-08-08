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
            # Stochastic rounding. This branch used to compute det_raw twice and
            # then append gf14_encode(val) anyway, so the result was thrown away
            # and stochastic=True was byte-identical to stochastic=False. Nothing
            # outside this file calls it, so nothing was ever wrong downstream --
            # the feature simply did not exist. The self-test now requires it to
            # differ from deterministic rounding on a block engineered to sit
            # between representable points.
            det_val = gf14_decode(gf14_encode(val))
            step = abs(det_val) * 2 ** (-GF14_M_BITS) if det_val != 0 else 2 ** (-14)
            noise = np.random.uniform(-step / 2, step / 2)
            raws.append(gf14_encode(val + noise))
        else:
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
    """SELF-TEST for GF-MX14. Assertions, not printouts.

    What was here before printed five sections of numbers, asserted NOTHING, and
    ended with an unconditional

        print("\u2713 GF-MX14 oracle: ALL TESTS PASS")

    That line runs whatever the numbers are. The oracle could decode every code to
    zero and it would still print a checkmark and the words ALL TESTS PASS. It is
    the purest form of the failure this campaign keeps finding: a claim of passing
    that is a constant.

    It was never caught because research/audit_selftest_sensitivity.py detected a
    self-test by searching for "SELF-TEST" or "self-test", and this file says
    "Self-Test". One capital letter kept the only oracle with no real self-test out
    of the gate built to find exactly that.

    Every bound below is derived from the format, never from what the code
    currently prints.
    """
    fails = []

    def check(cond, msg):
        if not cond:
            fails.append(msg)

    # GF14 carries an 8-bit stored mantissa rounded to nearest, so a normalized
    # in-range value round-trips to within half a ULP: 2**-9. The encoder also
    # clamps mant_raw to 255, which costs at most one further ULP when a value
    # rounds up into the next binade, so the guaranteed bound is 2**-8.
    BOUND = 2.0 ** -8

    check(gf14_decode(gf14_encode(0.0)) == 0.0, "zero does not round-trip")
    check(gf14_encode(0.0) == 0, "zero does not encode to the all-zero code")

    worst, worst_at = 0.0, None
    v = 1e-3
    while v < 1e3:
        for val in (v, -v):
            back = gf14_decode(gf14_encode(val))
            check((back < 0) == (val < 0) or back == 0.0,
                  f"sign not preserved at {val}")
            rel = abs(back - val) / abs(val)
            if rel > worst:
                worst, worst_at = rel, val
            check(rel <= BOUND, f"round-trip error {rel:.3e} > 2**-8 at {val}")
        v *= 1.0009
    print(f"   round-trip: worst relative error {worst:.3e} at {worst_at:.6g} "
          f"(bound 2**-8 = {BOUND:.3e})")

    # A block of one repeated value must dequantize to that value within the same
    # bound: the shared scale is exact, so nothing beyond element rounding happens.
    for val in (1.0, 0.1, 1e-5, 1e5, -7.25):
        blk = np.full(BLOCK_SIZE, val)
        scale, raws = quantize_block(blk)
        check(0 <= scale <= 255, f"E8M0 scale {scale} out of range for {val}")
        deq = dequantize_block(scale, raws)
        rel = np.max(np.abs(deq - blk) / abs(val))
        check(rel <= BOUND, f"uniform block of {val}: rel error {rel:.3e} > 2**-8")

    # An all-zero block must survive exactly, and must not produce a wild scale.
    scale, raws = quantize_block(np.zeros(BLOCK_SIZE))
    check(all(r == 0 for r in raws), "zero block did not encode to zero codes")
    check(np.all(dequantize_block(scale, raws) == 0.0), "zero block did not survive")

    # The shared scale is what buys dynamic range over bare GF14. On a block whose
    # values sit far below 1.0, bare GF14 flushes them and GF-MX14 must not.
    small = np.full(BLOCK_SIZE, 1e-6)
    check(gf14_decode(gf14_encode(1e-6)) == 0.0,
          "bare GF14 was expected to flush 1e-6 -- the premise of the scale changed")
    sc, rw = quantize_block(small)
    deq = dequantize_block(sc, rw)
    check(np.max(np.abs(deq - small) / 1e-6) <= BOUND,
          "GF-MX14 failed to represent a block bare GF14 cannot")

    # Stochastic rounding must actually round stochastically. The branch used to
    # discard its own result, making stochastic=True identical to deterministic.
    np.random.seed(7)
    mid = np.full(BLOCK_SIZE, 1.0 + 1.5 / (2 ** GF14_M_BITS))   # between two codes
    det = quantize_block(mid)[1]
    seen = set()
    for _ in range(20):
        seen.add(tuple(quantize_block(mid, stochastic=True)[1]))
    check(len(seen) > 1,
          "stochastic=True produced one fixed result -- the branch is inert again")
    check(any(t != tuple(det) for t in seen),
          "stochastic=True never differed from deterministic rounding")

    # find_block_scale: a round-trip alone cannot see a wrong scale, because
    # quantize and dequantize both use whatever it returned and the error cancels.
    # What a wrong scale DOES break is a block with spread: one binade too high and
    # the small elements flush to zero, one too low and the large ones saturate.
    #
    # The reachable span is fixed by the format, not by taste. GF14 has 5 exponent
    # bits and bias 15, and gf14_encode flushes exp <= 0, so a normalized value
    # survives while its encoded exponent is 1..30. find_block_scale places the
    # block maximum at unbiased exponent 14, i.e. encoded 29 -- so an element 2**-k
    # below the maximum flushes once k >= 29. Twenty-eight binades of within-block
    # range, and no more.
    #
    # The first version of this check asserted all 32 binades of a 32-element block
    # and failed. The assertion was wrong, not the code: a block spanning 2**-31 is
    # beyond what a 5-bit exponent can hold under one shared scale. That limit is a
    # property of microscaling worth pinning in both directions.
    IN_RANGE = 28
    spread = np.array([2.0 ** -k for k in range(IN_RANGE)] +
                      [2.0 ** -(IN_RANGE - 1)] * (BLOCK_SIZE - IN_RANGE))
    sc, rw = quantize_block(spread)
    deq = dequantize_block(sc, rw)
    check(np.count_nonzero(deq) == BLOCK_SIZE,
          f"an element within {IN_RANGE} binades of the block max was flushed")
    top = np.max(np.abs(deq - spread) / spread)
    check(top <= BOUND,
          f"block spanning {IN_RANGE} binades lost accuracy ({top:.3e}) -- "
          "scale misplaced")

    # And the other side of the same limit: 29 binades down does flush. Asserting
    # only the good half would let a scale drift upward unnoticed.
    over = np.full(BLOCK_SIZE, 1.0)
    over[-1] = 2.0 ** -29
    deq_over = dequantize_block(*quantize_block(over))
    check(deq_over[-1] == 0.0,
          "an element 29 binades below the max survived -- the reachable span "
          "moved, so the scale placement or the exponent width changed")

    # quantize_tensor must preserve shape and quantize blockwise, not globally.
    W = np.linspace(-1.0, 1.0, 4 * BLOCK_SIZE).reshape(4, BLOCK_SIZE)
    Wq = quantize_tensor(W)
    check(Wq.shape == W.shape, f"quantize_tensor reshaped {W.shape} to {Wq.shape}")
    nz = W != 0
    check(np.max(np.abs(Wq[nz] - W[nz]) / np.abs(W[nz])) <= BOUND,
          "quantize_tensor exceeded the element bound on a well-scaled tensor")

    # compute_quantization_error must report zero when nothing changed, and must
    # move when something does.
    m0 = compute_quantization_error(W, W)
    check(m0['max_rel_error'] == 0.0,
          f"error metric non-zero for identical inputs: {m0['max_rel_error']}")
    m1 = compute_quantization_error(W, Wq)
    check(m1['max_rel_error'] > 0.0, "error metric zero for a quantized tensor")
    check(m1['max_rel_error'] <= BOUND,
          f"metric reports {m1['max_rel_error']:.3e} above the element bound")

    # mx_mul_matrix quantizes only the left operand, so the product must track the
    # exact one to within the element bound times the condition of the sum.
    A = np.linspace(0.25, 1.0, 2 * BLOCK_SIZE).reshape(2, BLOCK_SIZE)
    B = np.ones((BLOCK_SIZE, 3), dtype=np.float32)
    got = mx_mul_matrix(A, B)
    check(got.shape == (2, 3), f"mx_mul_matrix shape {got.shape} != (2, 3)")
    exact = A @ B
    # All entries of A are positive, so no cancellation: the normwise bound is the
    # elementwise bound.
    check(np.max(np.abs(got - exact) / np.abs(exact)) <= BOUND,
          "mx_mul_matrix exceeded the element bound on a cancellation-free product")

    if fails:
        print(f"\nSELF-TEST FAILED: {len(fails)} check(s)")
        for f in fails:
            print(f"   {f}")
        return 1
    print("\nSELF-TEST: PASS  (round-trip, sign, uniform blocks, zero block, "
          "sub-GF14 range, stochastic rounding)")
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(_selftest())
