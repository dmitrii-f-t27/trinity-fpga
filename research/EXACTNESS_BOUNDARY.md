# The exactness boundary: one property, not three known limitations

Three things in this corpus have been recorded separately as caveats:

- `takum32` differs from libtakum by one ULP;
- `lns16`'s hardware proof reports `472/576 bit-exact, 104 known-limitation(s)`;
- numpy states 1–4 ULP tolerances for the same functions.

They are one property, and stating it as a property is stronger than apologising for it
three times.

## What the oracles actually hold

`conformance/takum_log_ref.py` does not return a number for a takum8 code. It returns

```python
Special(kind='exp', sign=0, ln=Fraction(-239, 2))
```

The natural logarithm is an **exact rational**. Every value in the format is
`sign · e^(ln)` with `ln` exactly known. `conformance/lns_ref.py` does the same through
`decode_log` and `encode_from_log`.

Measured across the published packs: of **407,145** takum and LNS vectors, **401,826**
have an operand of this kind — 98.7 %. That is not a coverage hole. It is the measurement
that these families are transcendental almost everywhere, and that the corpus represents
them **exactly** rather than approximately.

## Why hardware cannot match it, and why that is not a defect

Silicon emits fp32. Leaving the logarithmic domain means evaluating `exp()`, and `e^(p/q)`
for rational `p/q` is transcendental — no fixed-width binary float holds it. A 1-ULP
residual at the crossing is a **theorem**, not a bug in anyone's implementation.

This is why the takum and LNS conformance hosts carry their own goldens rather than
importing the oracle: the oracle's answer is a symbolic exponential, and a UART link
carries 32 bits. The host must cross the boundary to have anything to compare.

Three independent parties agree on where the boundary is:

| | says |
|---|---|
| the corpus oracle | exact in the log domain, declines a rational |
| libtakum, the reference implementation | differs from the oracle by one ULP after `exp()` |
| numpy | documents 1–4 ULP for `exp` |

Software oracle, third-party library and silicon all place the same line in the same
place. **Bit-exactness is attainable over the decidable class, and logarithmic evaluation
is not in it.**

## What a paper should say

Not *"104 known limitations"*, which reads as debt. Rather:

> The corpus is bit-exact wherever a format's values are rational, and exact in the
> logarithmic domain wherever they are not. For `takum` and `lns` the second case covers
> 98.7 % of the published vectors. Hardware conformance for those families is therefore
> stated to within one ULP of the correctly-rounded `exp()`, which is the best any
> fixed-width binary representation admits.

That is a sharper claim than bit-exactness everywhere, because it is true, and because it
says precisely which formats are which.

## What this does not excuse

The boundary explains 1-ULP residuals at a transcendental crossing. It does **not** explain:

- a decoder that returns zero where the reference has 2.6e-28 (`takum8`, 11 codes);
- a decoder that returns infinity where the reference has 3.8e27 (`takum8`, 7 codes);
- a format that cannot represent 1 (`lns16` hardware, pass 204).

Those are open questions about conventions, not about arithmetic, and this document is not
a place to file them.
