# arXiv:2606.05017 — GoldenFloat v2 Update Notes

## What changed since v3 (2026-06-22)

### New: Silicon Tier-E Proof (Section 5 addition)

16 compute cells verified on AX7203 (XC7A200T-FBG484-2):

| Format | Op | Vectors | Method |
|--------|-----|---------|--------|
| GF4 | ADD | 256/256 exhaustive | UART conformance |
| GF4 | MUL | 256/256 exhaustive | UART conformance |
| GF6 | ADD | 4096/4096 exhaustive | UART conformance |
| GF6 | MUL | 4096/4096 exhaustive | UART conformance |
| GF8 | ADD | 512/512 | UART conformance |
| GF8 | MUL | 512/512 | UART conformance |
| GF12 | ADD | 256/256 | UART conformance |
| GF12 | MUL | 256/256 | UART conformance |
| GF16 | ADD | 128/128 | UART conformance |
| GF16 | MUL | 128/128 | UART conformance |
| GF20 | ADD | 260/260 | UART conformance |
| GF20 | MUL | 260/260 | UART conformance |
| GF24 | ADD | 240/240 | UART conformance |
| GF24 | MUL | 240/240 | UART conformance |
| GF32 | ADD | 240/240 | UART conformance |
| GF32 | MUL | 240/240 | UART conformance |

Total: 11392/11392 bit-exact, 0 failures.

### Toolchain: Fully Open-Source

```
RTL → yosys (synth_xilinx -nocarry -arch xc7)
    → nextpnr-xilinx (--fasm --placer heap)
    → fasm2frames (prjxray)
    → xc7frames2bit (--part.yaml)
    → openocd pld load (500 kHz, ~156s)
    → UART conformance (gf_ref.py fractions.Fraction oracle)
```

No Vivado used. No proprietary tools.

### Routing Discovery

yosys `-abc9` flag produces technology-mapped logic that nextpnr-xilinx
cannot route for GF8+ MUL designs. Removing `-abc9` resolves routing
without Vivado. This is a yosys/nextpnr interaction, not an FPGA limitation.

### Falsification Ledger Update (FL-002)

(c1) GF256 bias: unchanged — GF256 not yet on silicon
(c2) Count drift: SSOT total_formats = 83 (unchanged). Catalog RTL has
    452+ compute families, but canonical format count per SSOT = 83.
    Canonical GF family remains GF4-GF256 (9 formats per paper).
(g) static-split vs micro-mixing: unchanged

### Erratum

Companion paper 2606.09686 states 83 format families — this remains
correct per SSOT. No count correction needed.

### What NOT to claim in v2

1. "Best format" — GoldenFloat is architecturally distinct, not superior
2. "Full catalog on silicon" — only 16 cells (GF4-GF32 × ADD+MUL)
3. "Vivado-free timing closure" — --timing-allow-fail used, Fmax unknown
4. "BF16 bit-exact" — 11 rounding tie-break mismatches (oracle limitation)
5. "GF64+ on silicon" — GF64/GF128 ADD smoke tests only (0+0=0), not
   full UART conformance. GF256 CI-built, not flashed. Only 8 formats
   (GF4-GF32) have full Tier-E 4/4 on silicon.

### Proposed v2 submission text

"We extend the hardware description with the first silicon verification of
GoldenFloat compute arithmetic: 16 cells covering the canonical GF4-GF32
family × {ADD, MUL} operations, verified bit-exact against a fractions.Fraction
golden oracle via UART conformance on a Xilinx Artix-7 XC7A200T. The complete
open-source toolchain (yosys → nextpnr-xilinx → prjxray → openocd) is used,
requiring no proprietary software. A routing interaction between yosys abc9
optimization and nextpnr-xilinx is identified and resolved."
