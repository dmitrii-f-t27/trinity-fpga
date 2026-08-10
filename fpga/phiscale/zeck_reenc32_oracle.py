#!/usr/bin/env python3
"""Independent oracle for zeck_reenc32, checked against a SAMPLE of its inputs.

zeck_reenc16 could be swept whole: 65,536 inputs, all of them checked. This unit
takes 32 bits, so the space is 4,294,967,296 and a sweep is out of reach here.
Everything this script prints is therefore a statement about a sample. It says
so on every run, and the word "exhaustive" appears nowhere in its verdict. A
passing run means: no counterexample was found among the vectors supplied.

The oracle is written from the definition -- greedy subtraction over the
Fibonacci numbers -- and not from the Verilog. A model transcribed from the
design under test agrees with the design's bugs.

Four properties, all required of every vector:
  1. sum      : the digits weigh back to the input
  2. adjacency: no two adjacent ones, which is what makes the encoding canonical
  3. model    : the digits are the ones greedy subtraction produces
  4. range    : no digit above the 46 that exist

Plus three coverage checks on the sample as a whole, because a sample that
misses the hard cases proves nothing:
  5. every directed input the definition demands is present:
     0, 1, every Fibonacci number below 2^32, each of those minus and plus one,
     and the maximum 2^32-1
  6. every one of the 46 compare-subtract stages was seen both taken and
     not taken
  7. some input carried the densest Zeckendorf word the range allows, which is
     the longest carry chain that exists for this width

Usage:  python3 zeck_reenc32_oracle.py <vvp-output>
Exit 0 only if every vector passes 1-4 and every coverage check passes.
"""
import sys
from pathlib import Path

WIDTH = 32
DIGITS = 46
SPACE = 1 << WIDTH
MAXV = SPACE - 1


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


def required_directed() -> set:
    """The directed inputs the definition demands, independent of the testbench."""
    req = {0, 1, MAXV}
    for f in F:
        for v in (f - 1, f, f + 1):
            if 0 <= v <= MAXV:
                req.add(v)
    return req


def densest() -> int:
    """Most ones a Zeckendorf word can carry inside [0, 2^32-1].

    Ones are cheapest at the bottom and may not be adjacent, so the densest
    word is 1 + 3 + 8 + 21 + ... taken while it still fits.
    """
    total, n = 0, 0
    for i in range(0, DIGITS, 2):
        if total + F[i] > MAXV:
            break
        total += F[i]
        n += 1
    return n


def parse(path: Path):
    """Strict parse: blank and '#' lines are commentary, everything else is data.

    Anything else that fails to parse is an error rather than a skip -- a
    truncated or garbled capture must not be able to pass by being ignored.
    """
    pairs, bad = [], []
    for lineno, ln in enumerate(path.read_text().split("\n"), 1):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split()
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            bad.append((lineno, s[:60]))
            continue
        pairs.append((int(parts[0]), int(parts[1])))
    return pairs, bad


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit("usage: zeck_reenc32_oracle.py <vvp-output>")
    pairs, bad = parse(Path(sys.argv[1]))

    if bad:
        print(f"  FAIL: {len(bad)} unparsable line(s), first at line "
              f"{bad[0][0]}: {bad[0][1]!r}")
        return 1
    if not pairs:
        print("  FAIL: no vectors in the capture")
        return 1

    sum_bad, adj_bad, model_bad, rng_bad = [], [], [], []
    taken = [0] * DIGITS
    nottaken = [0] * DIGITS
    max_ones = 0
    for x, z in pairs:
        if x > MAXV:
            rng_bad.append((x, z))
            continue
        if z >> DIGITS:
            rng_bad.append((x, z))
        if weigh(z) != x:
            sum_bad.append((x, z))
        if z & (z >> 1):
            adj_bad.append((x, z))
        if z != greedy(x):
            model_bad.append((x, z))
        for i in range(DIGITS):
            if z >> i & 1:
                taken[i] += 1
            else:
                nottaken[i] += 1
        max_ones = max(max_ones, bin(z).count("1"))

    n = len(pairs)
    distinct = {x for x, _ in pairs}
    req = required_directed()
    missing_req = sorted(req - distinct)
    stages_taken = sum(1 for c in taken if c)
    stages_not = sum(1 for c in nottaken if c)
    want_ones = densest()

    frac = 100.0 * len(distinct) / SPACE
    print(f"  vectors checked       : {n}")
    print(f"  distinct inputs       : {len(distinct)}")
    print(f"  input space           : {SPACE}")
    print(f"  coverage              : {frac:.6f}% -- SAMPLE, NOT EXHAUSTIVE")
    print(f"  sum property          : {n - len(sum_bad)}/{n}")
    print(f"  no-two-adjacent-ones  : {n - len(adj_bad)}/{n}")
    print(f"  matches greedy oracle : {n - len(model_bad)}/{n}")
    print(f"  digits in range       : {n - len(rng_bad)}/{n}")
    print(f"  required directed set : {len(req) - len(missing_req)}/{len(req)}")
    print(f"  stages seen taken     : {stages_taken}/{DIGITS}")
    print(f"  stages seen not taken : {stages_not}/{DIGITS}")
    print(f"  longest carry chain   : {max_ones} ones (densest possible "
          f"is {want_ones})")

    for name, lst in (("sum", sum_bad), ("adjacency", adj_bad),
                      ("oracle", model_bad), ("range", rng_bad)):
        if lst:
            x, z = lst[0]
            g = greedy(x) if x <= MAXV else 0
            print(f"  first {name} failure: x={x} z={z:#048b} "
                  f"weighs {weigh(z & (2**DIGITS - 1))}, greedy says {g:#048b}")
    if missing_req:
        print(f"  missing directed inputs ({len(missing_req)}), first few: "
              f"{missing_req[:6]}")
    if max_ones != want_ones:
        print("  no vector reached the densest Zeckendorf word")

    ok = not (sum_bad or adj_bad or model_bad or rng_bad or missing_req)
    ok = ok and stages_taken == DIGITS and stages_not == DIGITS
    ok = ok and max_ones == want_ones
    print("  VERDICT:", "PASS on this sample" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
