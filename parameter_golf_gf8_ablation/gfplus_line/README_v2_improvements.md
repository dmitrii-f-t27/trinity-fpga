# GF+A v2 — improvements along vectors 1+3+4 (loop 22.07.2026)

`[measured — SW proxy, CPU]` for vectors 1+3; `[measured CI-synth, yosys generic]` for vector 4.
seed=20260722, harness `testD_v2.py`, RTL `../../fpga/openxc7-synth/gfplus8_a_decode.v`.

## What was (v1, the reference point)

GF+A v1 (inv. #15): per-row absmax **fp16 scale** (16 bits/row) + a **2-bit header on EACH row**,
pockets `{φ-split, e2, e3, INT}`. Three holes:
1. container overhead ~0.094 bits/element (at C=192) — eats the margin on uniform weights;
2. guarantee only on MSE, not downstream;
3. the decoder LUT cost has not been measured.

## Vector 1 — cheaper overhead (e8m0-scale + group header)

- **e8m0-scale**: per-row scale as an 8-bit exponent (power of two, rounded up) instead of fp16.
  For per-row absmax the scale mantissa is almost unnecessary.
- **group header**: 1 pocket choice per block of K rows (the pocket rarely changes between
  neighbors).

Result (real micro-LM weights, class 8 bit, C=192):

| variant | ΔBPB | SQNR_W1 | overhead bits/el | eff. bits |
|---|---|---|---|---|
| v1 (fp16 scale, K=1) | −0.0000 | 43.89 | 0.0938 | 8.094 |
| v2 e8m0 scale, K=1 | −0.0000 | 43.89 | 0.0521 | 8.052 |
| v2 e8m0 scale, K=8 | +0.0000 | 43.51 | 0.0430 | 8.043 |
| v2 e8m0 scale, K=32 | −0.0000 | 43.44 | 0.0420 | **8.042** |

**Conclusion:** overhead reduced from 0.094 to 0.042 bits/element (**−55%**) with no ΔBPB loss.
SQNR at K=32 drops by ~0.45 dB (the group header sacrifices selection granularity) —
**K=8 = a reasonable compromise** (SQNR −0.38 dB, overhead −54%).

## Vector 3 — living pockets (lns instead of the dead φ-e3m4)

By the v1 measurement the φ-e3m4 pocket took ~0 rows on 8-bit (a dead slot). Replaced with **lns8**
(logarithmic — strong on heavy tails). Liveness check (synthetic, row selection):

| distribution | 8-bit pocket selection v2 |
|---|---|
| gauss | e2m5:511, int8:1 |
| heavy | phi_e3m4:111, **e2m5:390, lns8:11** |
| uniform | int8:512 |
| mixed_outlier | phi_e3m4:49, e2m5:459, int8:2, **lns8:2** |

**Conclusion:** the lns-pocket is active on `heavy`/`mixed_outlier` (heavy tails) — the 4th slot
has stopped being dead. On uniform micro-LM weights lns is almost never selected — its value is
insurance on heterogeneous data, NOT a gain on uniform data (consistent with the honest framing of
inv. #15).

## Vector 4 — decoder LUT cost (was `[open hypothesis]`)

RTL of the 4-pocket decoder `gfplus8_a_decode.v` (pockets 00=phi_e3m4, 01=e2m5, 10=int8, 11=lns8;
2-bit header → mux). Independent witness: iverilog dump of 1024 vectors checked against the Python
reference — **255/256 bit-for-bit per pocket**, the only discrepancy = −0.0 vs +0.0 (word=128),
mathematically equivalent (the RTL correctly preserves the sign of zero). yosys
`synth_xilinx -flatten` (generic, NOT P&R):

| decoder | LUT | MUXF | CARRY4 |
|---|---|---|---|
| GF+A 4-pocket 8-bit | 53 | 21 | 6 |
| e2m5 single 8-bit | 32 | 19 | 2 |

**Conclusion `[measured CI-synth, yosys generic]`:** adaptivity costs **+21 LUT (1.66×)** vs a
single e2m5 of the same class. The price of flexibility is ~two thirds extra area. Final LUT/Fmax =
openXC7 P&R on AX7203 `[REQUIRES USER ACTION]` (yosys generic ≠ P&R on the board).

## Honest summary for the paper

- GF+A v2 reduces container overhead by 55% (e8m0-scale + group header K=8);
- the 4th pocket (lns8) is active on heavy tails — adaptivity = insurance, not a gain on uniform
  weights;
- the price of adaptivity is measured for the first time: +21 LUT (1.66×) vs a single e2m5
  `[yosys generic]`.
- boundaries: 1 micro-LM checkpoint, C=192; ΔBPB of classes ≥6 bit ±0.0003 (SQNR ranks, not BPB);
  final area requires P&R on the board.

## Artifacts

- `gfplus_adaptive_v2.py` — e8m0-scale, group header, v2 pocket catalog (lns-slot);
- `testD_v2.py` + `testD_v2_results.json` — measurements of vectors 1+3;
- `../../fpga/openxc7-synth/gfplus8_a_decode.v` + `_tb.v` — RTL decoder + testbench (vector 4).
