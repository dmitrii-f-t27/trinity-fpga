"""Regime fields as universal codes for the exponent: build, normalise, compare.

Backs Theorems 11-13 of the Ternary Floats paper. Each regime is a codeword-length
function; norm() adds the smallest constant making it satisfy Kraft, after which
M_eff(e) = N - 1 - l(e) exactly.
"""
import math
EMAX = 100_000

def norm(l, emax=EMAX):
    """Smallest constant c with sum over +-e of 2^-(l(e)+c) <= 1."""
    for c in range(12):
        if sum(2.0 ** -(l(e) + c) for e in range(1, emax)) * 2 <= 1.0:
            return lambda e, c=c: l(e) + c
    raise ValueError("no constant makes this code Kraft-feasible")

REGIMES = {
    "unary":     lambda e: e // 4 + 3,                              # posit class
    "sqrt":      lambda e: math.ceil(math.sqrt(e)) + 2,             # the gap
    "log2":      lambda e: int(math.log2(e)) + 3,                   # takum class
    "trit3":     lambda e: math.ceil(math.log(e, 3) * math.log2(3)) + 3,
}

def meff(l, N, e):
    return N - 1 - l(e)

def binades(l, N):
    for e in range(1, EMAX):
        if N - 1 - l(e) < 1:
            return e - 1
    return EMAX

if __name__ == "__main__":
    R = {k: norm(v) for k, v in REGIMES.items()}
    # Theorem 13: log2 and trit3 differ by an additive constant, not a growth rate
    d = {R["log2"](e) - R["trit3"](e) for e in (1, 4, 16, 64, 256, 1024, 4096)}
    assert len(d) == 1, f"radix invariance violated: {d}"
    print(f"radix invariance: log2 - trit3 = {d.pop()} at every |e| tested")
    for N in (16, 32):
        print(f"\nN={N}")
        for k, l in R.items():
            row = " ".join(f"{meff(l,N,e):4d}" for e in (1, 4, 16, 64, 256))
            print(f"  {k:6s} {row}   {binades(l,N):6d} binades")
