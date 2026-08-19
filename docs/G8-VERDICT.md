# G8 verdict: the sixteen untraced frequencies, measured on CI (run 32263875250)

Instrument: `tnf-format-throughput` (#618, hardened by #620/#622). All 19
tnet tract arms ROUTED on xc7a200tfbg484-2 — the first post-route rows this
gate has ever had. Comparison band: the audited seed dispersion for this
toolchain, 1.6–41.7 %; "reproduced" below means WITHIN-NOISE, never equality.

## The verdict, row by row

**14 of 15 instrumented rows reproduce within the band** (CI/published
0.90×–1.32×): binary16 1.00×, int8 0.97×, binary32 0.97×, VAX F 0.93×,
GF10 0.95×, GF14 0.90×, GFTernary 0.90×, fp8 e4m3 1.06×, fp8 e5m2 1.09×,
takum16 1.09×, IBM hex32 1.11×, posit8 1.14×, posit16 1.19×, posit32 1.32×.

**One row does NOT reproduce: LNS16 — CI 62.66 MHz vs published 43.04 MHz
(1.46×, outside the band).** The published figure has no in-tree record
(MATRIX.md's corrected rerun does not include LNS16); the CI row is now the
only sourced number for this format. Author input needed: original log, or
the paper's row is superseded by the CI measurement.

**One row is uninstrumented: "plastic 16-bit, 318.47 MHz"** — a
tab:hierarchy design, not a tnet tract; no harness in the sweep.

Correction to G8-INSTRUMENT-MAP.md: IBM hex32 DOES have an in-tree harness
(`s_ibmhfp.v`) — it routed at 51.72 MHz, 1.11× of the published 46.78.

## What this does to the gate

G8 asked for post-route evidence behind sixteen published frequencies that
had none. Fifteen now have CI-sourced rows; fourteen agree within the
toolchain's own measured noise. The remaining asks are narrow and named:
LNS16 (one number, author or supersede) and plastic-16bit (one harness).
The gate's status moves from "unsourced" to **measured-with-two-exceptions**.
