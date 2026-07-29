# gf24/gf32 decode — pipelined variant + iverilog witness (horizon-B routing prep)

**Date:** 2026-07-24. **Author:** Vasilev (gHashTag), ORCID 0009-0008-4294-6159.
**Status:** `[verified SW on iverilog]` (function). Synth/PnR/flash on AX7203 = `[REQUIRES USER ACTION]`.

## Why

gf24 (E9/M14/BIAS255) and gf32 (E12/M19/BIAS2047) decode **fail routing**
on AX7203 (XC7A200T) when synthesized from the purely combinational `gf_decode_param.v`
(no-flatten CI = FAILURE, runs 28773511637 / 28773514467). The reason is
**NOT a giant LUT-table** (unlike takum, which was fixed by split-BRAM),
but the **depth of a single combinational cloud**: a variable barrel-shift (up to ~40 bits)
+ a dynamic sticky-mask + CLZ + rounding in a single `always@(*)`. The correct
horizon-B technique here is **datapath pipelining**, not table splitting.

## What was done

- `fpga/openxc7-synth/gf_decode_param_pipe.v` — a 2-stage pipeline of the same
  decode-law (latency 2 cycles). The register is inserted AFTER classification +
  true_exp + shift computation, BEFORE the barrel-shift + rounding + FP32-pack.
  **The arithmetic is bit-for-bit identical** to `gf_decode_param.v` (the same iverilog-fixes:
  widen-before-shift #1, `[23:0] sub_shifted` OOB-read #2). ONLY the temporal structure
  changed, not the function.

## Proof (independent 2nd witness)

- `gf_decode_pipe_oracle.py` — golden Fraction-oracle gf{N}→FP32 (exact rational decode
  + RNE to binary32). **Structurally independent** of the Verilog.
  Self-checked: `oracle_selfcheck.py` = 200k fp32 round-trips bit-for-bit vs numpy.
- `tb_gf_decode_param_pipe.v` — a self-checking iverilog-bench (one vector at a time with
  a full pipeline reset, no streaming ambiguity).

### Results (iverilog 12.0)

| Format | Fields | Vectors | Result |
|---|---|---|---|
| gf24 | E9/M14/BIAS255 | 30000 (repr.+5-class corners) | **30000/30000 bit-exact** |
| gf32 | E12/M19/BIAS2047 | 30000 (repr.+5-class corners) | **30000/30000 bit-exact** |

Control: the purely combinational `gf_decode_param.v` on the same vectors = 30000/30000
(the oracle agrees with both the original and with numpy — a triple check).

yosys generic synth (`synth -flatten`, gf32): 1927 cells, 73 FF (2 stages confirmed).
**This is `[simulated]`, NOT P&R** — a routing verdict is only given by openXC7 on the board.

## Reproduce

```bash
cd conformance/witness/gf_pipe
python3 oracle_selfcheck.py                                   # oracle vs numpy
python3 gf_decode_pipe_oracle.py --N 24 --E 9  --M 14 --BIAS 255  --count 30000 --out vec_gf24.txt
python3 gf_decode_pipe_oracle.py --N 32 --E 12 --M 19 --BIAS 2047 --count 30000 --out vec_gf32.txt
iverilog -g2012 -DN=24 -DE=9  -DM=14 -DBIAS=255  -DVEC='"vec_gf24.txt"' -DNVEC=30000 \
  -o s24.vvp ../../../fpga/openxc7-synth/gf_decode_param_pipe.v tb_gf_decode_param_pipe.v && vvp s24.vvp
iverilog -g2012 -DN=32 -DE=12 -DM=19 -DBIAS=2047 -DVEC='"vec_gf32.txt"' -DNVEC=30000 \
  -o s32.vvp ../../../fpga/openxc7-synth/gf_decode_param_pipe.v tb_gf_decode_param_pipe.v && vvp s32.vvp
```

## Honest boundaries

- This is a **hypothesis** for a routing fix: the pipeline shortens the critical path, but
  whether gf24/gf32 pass P&R on Artix-7 is **verifiable ONLY on the board**
  (openXC7 nextpnr-xilinx is unavailable in the sandbox). `[routing-pending]`.
- iverilog proves the **function** (encoding decode), NOT Tier-E. Tier-E = the full
  4/4 chain (CI GREEN + SHA256 + UART N/N fails=0 @160000 + IDCODE 0x13636093).
- Latency grew from 0 (comb.) / 1 (OUT_REG) to 2 cycles — the host UART-conformance script
  must account for the 2-cycle delay when reading the result.
- Representative sample (30k + 5-class corners), NOT exhaustive (gf32 = 2³²
  is unreachable in the sandbox; full gf24 = 2²⁴ = 16.7M is possible on the board).
