# The cost of non-closure, measured

Corollary `cor:closure` says a representable set that is not closed under its
own operation needs a stage returning results to the set. This measures that
stage on the fabric the decoder table was measured on: isolated unit, every
output bit folded into the observed reduction, median of five placement seeds,
Yosys 0.65 + nextpnr-xilinx 1743d0f, xc7a200t.

## One accumulation step

| | LUT | Fmax (median of 5) |
|---|---|---|
| closed -- `Z[phi]`, componentwise | **182** | **299.94 MHz** |
| non-closed -- normalise back into the set | 1756 | 11.46 MHz |
| **cost of non-closure, 16-bit** | **x9.6 area** | **/26.2 frequency** |
| closed -- `Z[phi]`, componentwise (32-bit) | **283** | **239.35 MHz** |
| non-closed -- normalise back (32-bit) | 7017 | 4.25 MHz |
| **cost of non-closure, 32-bit** | **x24.8 area** | **/56.3 frequency** |

Seed spread: 0.20--0.25 MHz on the non-closed units, 16.85--59.39 MHz on the
closed ones. The closed units are fast enough that placement noise is visible;
the non-closed ones are so far from the constraint that every seed lands in the
same place.

The non-closed 32-bit unit **fails** the 12 MHz bench constraint. The closed one
passes it twenty-fold.

## Why accumulation and not multiplication

The first version of this measurement compared weight *application*, and it was
the wrong place to look. A weight can be applied either way. What cannot be
avoided is that a neural layer accumulates, at fan-in 512 per neuron, and:

- In `Z[phi]` the sum of two ring elements is a ring element. The accumulator is
  a pair of integer registers and addition is componentwise -- the same cost as
  any integer accumulator, and exact.
- In a Fibonacci/Zeckendorf representation the sum of two representable numbers
  is **not** representable. `F_3 + F_3 = 4 = F_4 + F_1`: the representation
  changes non-trivially. Every accumulation must be renormalised.

So the stage does not run once per multiply. It runs once per accumulation, 512
times per neuron, and that is the number above.

## What this does and does not establish

**Does.** For the straightforward normaliser -- greedy Zeckendorf, oracle-checked
at 40/40 for both the sum and the no-two-adjacent-ones property -- returning to
a non-closed set costs an order of magnitude more area than the entire closed
accumulation, and two orders on frequency.

**Does not.** It is not a reimplementation of FQP, whose units are not public in
detail; it measures the structural cost their number set imposes, not their
design. Greedy is not proven to be the cheapest normaliser -- constant-time
Zeckendorf adders exist -- so the *ratio* is an upper bound on this
implementation while the *qualitative* claim (some stage is required; the closed
path requires none) is what the corollary proves. And part of the frequency gap
is combinational depth, 46 dependent stages against one addition; pipelining
converts that into latency and registers rather than removing it.

## The self-caught strawman

The first opponent built here was greedy Zeckendorf applied to weight
application, and it would have been a strawman: the identity
`F_m F_n = (L_{m+n} - (-1)^n L_{m-n})/5` -- verified over 300 index pairs before
any RTL was written -- turns a product into two Lucas-table lookups, a subtract
and a divide by five. Far cheaper than 46 compare-subtract stages.

Finding that identity is what showed the measurement was aimed at the wrong
operation. The comment at the top of our own `phi_step.v` had already stated the
rule -- *an unmatched comparison is wrong whichever way it points* -- and the
first draft of this measurement broke it in our favour.

**T27.** Build the opponent's strongest form before measuring, not their most
obvious one. The search for their best case is also the check on whether you are
measuring the right operation: the identity that would have rescued them is what
revealed that products were never where their cost lived.
