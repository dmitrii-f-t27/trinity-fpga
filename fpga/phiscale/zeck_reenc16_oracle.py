#!/usr/bin/env python3
"""Independent oracle for zeck_reenc16, checked against every input it accepts.

Written because the number in circulation was "oracle-checked 40/40", and no
oracle was in the repository: grep for zeckendorf across the Python, Zig and
Rust found nothing, and the only script ever committed beside the design was an
area/frequency sweep with no pass/fail count in it. Forty vectors against a
2^16 space is a spot check in any case, and this space is small enough to sweep
whole.

The oracle is written from the definition -- greedy subtraction over the
Fibonacci numbers -- and not from the Verilog. A model transcribed from the
design under test agrees with the design's bugs.

Two properties, both required:
  1. sum      : the digits weigh back to the input
  2. adjacency: no two adjacent ones, which is what makes the encoding canonical

Usage:  python3 zeck_reenc16_oracle.py <vvp-output>
Exit 0 only if every input passes both.
"""
import sys
from pathlib import Path

WIDTH = 16
DIGITS = 23


def fibs(n_digits: int) -> list:
    """d[0]..d[n-1] weigh 1, 2, 3, 5, 8, ... -- Fibonacci from F(2) upward."""
    f = [1, 2]
    while len(f) < n_digits:
        f.append(f[-1] + f[-2])
    return f[:n_digits]


F = fibs(DIGITS)


def greedy(x: int) -> int:
    """Greedy Zeckendorf digits as an integer bitmask, MSB = largest Fibonacci."""
    d = 0
    r = x
    for i in range(DIGITS - 1, -1, -1):
        if r >= F[i]:
            r -= F[i]
            d |= 1 << i
    assert r == 0, f"greedy left a remainder for {x}"
    return d


def weigh(d: int) -> int:
    return sum(F[i] for i in range(DIGITS) if d >> i & 1)


def main() -> int:
    if len(sys.argv) < 2:
        return int(bool(sys.exit("usage: zeck_reenc16_oracle.py <vvp-output>")))
    lines = Path(sys.argv[1]).read_text().split("\n")
    seen = {}
    for ln in lines:
        parts = ln.split()
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        seen[int(parts[0])] = int(parts[1])

    total = 1 << WIDTH
    missing = [x for x in range(total) if x not in seen]
    if missing:
        print(f"  FAIL: {len(missing)} of {total} inputs never appeared "
              f"(first: {missing[:4]})")
        return 1

    sum_bad, adj_bad, model_bad = [], [], []
    for x in range(total):
        z = seen[x]
        if weigh(z) != x:
            sum_bad.append(x)
        if z & (z >> 1):
            adj_bad.append(x)
        if z != greedy(x):
            model_bad.append(x)

    print(f"  inputs swept          : {total} of {total} (exhaustive)")
    print(f"  sum property          : {total - len(sum_bad)}/{total}")
    print(f"  no-two-adjacent-ones  : {total - len(adj_bad)}/{total}")
    print(f"  matches greedy oracle : {total - len(model_bad)}/{total}")
    for name, bad in (("sum", sum_bad), ("adjacency", adj_bad), ("oracle", model_bad)):
        if bad:
            x = bad[0]
            print(f"  first {name} failure: x={x} z={seen[x]:#025b} "
                  f"weighs {weigh(seen[x])}, greedy says {greedy(x):#025b}")
    ok = not (sum_bad or adj_bad or model_bad)
    print("  VERDICT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
