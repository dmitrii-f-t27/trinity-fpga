# IGLA RACE — full map of repositories and tasks

## Repositories (4 main)

| Repo | Description | Role |
|------|---------|------|
| **trios-trainer-igla** | Training pipeline (Rust) | SSOT: model, optimizer, BPB telemetry |
| **trios-railway** | Railway deployment + gardener | Auto-deploy, heartbeat, champion tracking |
| **trios-mcp** | MCP server (Rust) | AI agent interface to tri CLI |
| **trinity-fpga** (this repo) | FPGA hardware | GF16+ silicon, format catalog |

## Current IGLA RACE status

```
Champion:  gf256 × adamw = BPB 2.5719 (frozen since May 14)
Target:    BPB < 1.50 on 3 seeds
Gap:       -1.07 BPB
```

## Key Issues (30 tasks)

### trios-trainer-igla (29 issues)

**OPEN — critical:**
- #217: nf4 kernel does not train (delta_bpb=0.0)
- #123: Postgres pool exhausted (68 services)
- #181: φ as falsifiable architecture prior
- #97: Phase-2/3 QAT (stochastic rounding + non-IEEE)
- #93: canonical canon_name format spec

**CLOSED — completed:**
- #95: fake_quant exponent/range bugs fixed
- #110: SOAP optimizer added (9-axis grid complete)
- #118: BIGINT step columns
- #84: requeued phi-LR canon_name bug

### trios-railway (18 issues)

**OPEN:**
- #230: doctor-loop failing (PAT expired)
- #229: Cycle-19 active lanes
- #175: champion stall (gf256 BPB 2.5719)
- #177: local fleet decommissioned

**CLOSED:**
- #182: format CHECK constraint expanded (now supports gf4/gf8/gf32/gf64 + 49 formats)
- #173: JEPA × adamw × h=256 = 5.9675 (beats entire bigram matrix)
- #174: GF8 negative control (8/9 optimizers dead at init h=128)

### t27 — IGLA CODER+RACE (22 wave loops)

| Wave Loop | Achievement |
|-----------|-----------|
| 358 | 176 ∀ theorems, 546/546 PASS |
| 359-360 | Ternary MAC synthesis attempt |
| 361-362 | First OpenXC7 ternary MAC bitstream + board flash |
| 363-370 | gen-verilog fixes (width correctness) |
| 371-380 | Tuple-return generation, 312 generic ∀ |

### t27 — IGLA-Coder Phases (5 tasks)

| Phase | Task | Status |
|-------|--------|--------|
| P4 (#1037) | Pilot pretraining 50-200M | Open |
| P5 (#1038) | Multi-language eval | Open |
| P6 (#1039) | Scale to 0.5B-1.5B | Open |
| P7 (#1040) | Low-bit/ternary track | Open |
| P8 (#1041) | Integration + publication | Open |

## IGLA RACE format matrix

| Format | BPB (adamw) | BPB (muon) | delta | Status |
|--------|-------------|------------|-------|--------|
| **gf256** | **2.5719** | — | — | **CHAMPION** |
| gf16 | 6.975 | 6.975 | 0.026 | Works |
| fp8_e4m3 | 6.668 | — | 0.333 | Works |
| int4 | — | 6.695 | 0.304 | Works (STE) |
| int8 | — | 6.903 | 0.096 | Works |
| nf4 | 7.000 | 7.000 | **0.000** | **Does not train** (#217) |

## Connection with our GF16+

```
IGLA RACE uses:          gf256 (champion), gf16, fp8, int4, int8
Our contribution (GF16+):  100% gradient survival (vs gf16's 64%)
                          Silicon proven: dot product 8.0 ✓
                          Golden Ruler: #1 recommendation for training

What WE can give IGLA RACE:
  1. GF16+ → replaces gf16 (exact Quire accumulation, 0 gradient loss)
  2. Golden Ruler → auto-selection of format for the workload
  3. Format catalog (72/83) → expand the test matrix
  4. Coq invariants INV-3/INV-5 → formal verification of GF16 safe domain
```

## What needs to be done (plan)

1. **Clone trios-trainer-igla** → add GF16+ as a format
2. **Fix nf4 (#217)** → add scale + STE (similar to our fake_quant fix)
3. **Run GF16+ on IGLA RACE** → compare BPB with gf16
4. **Email Hunhold** → joint paper with a takum benchmark
