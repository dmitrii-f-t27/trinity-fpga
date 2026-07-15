# IGLA RACE — полная карта репозиториев и задач

## Репозитории (4 основных)

| Репо | Описание | Роль |
|------|---------|------|
| **trios-trainer-igla** | Training pipeline (Rust) | SSOT: модель, оптимизатор, BPB telemetry |
| **trios-railway** | Railway deployment + gardener | Auto-deploy, heartbeat, champion tracking |
| **trios-mcp** | MCP server (Rust) | AI agent interface to tri CLI |
| **trinity-fpga** (этот репо) | FPGA hardware | GF16+ silicon, format catalog |

## Текущий статус IGLA RACE

```
Champion:  gf256 × adamw = BPB 2.5719 (frozen since May 14)
Target:    BPB < 1.50 on 3 seeds
Gap:       -1.07 BPB
```

## Ключевые Issues (30 задач)

### trios-trainer-igla (29 issues)

**OPEN — критические:**
- #217: nf4 kernel не тренируется (delta_bpb=0.0)
- #123: Postgres pool exhausted (68 services)
- #181: φ as falsifiable architecture prior
- #97: Phase-2/3 QAT (stochastic rounding + non-IEEE)
- #93: canonical canon_name format spec

**CLOSED — выполненные:**
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

| Wave Loop | Достижение |
|-----------|-----------|
| 358 | 176 ∀ theorems, 546/546 PASS |
| 359-360 | Ternary MAC synthesis attempt |
| 361-362 | First OpenXC7 ternary MAC bitstream + board flash |
| 363-370 | gen-verilog fixes (width correctness) |
| 371-380 | Tuple-return generation, 312 generic ∀ |

### t27 — IGLA-Coder Phases (5 tasks)

| Phase | Задача | Статус |
|-------|--------|--------|
| P4 (#1037) | Pilot pretraining 50-200M | Open |
| P5 (#1038) | Multi-language eval | Open |
| P6 (#1039) | Scale to 0.5B-1.5B | Open |
| P7 (#1040) | Low-bit/ternary track | Open |
| P8 (#1041) | Integration + publication | Open |

## Форматная матрица IGLA RACE

| Format | BPB (adamw) | BPB (muon) | delta | Статус |
|--------|-------------|------------|-------|--------|
| **gf256** | **2.5719** | — | — | **CHAMPION** |
| gf16 | 6.975 | 6.975 | 0.026 | Работает |
| fp8_e4m3 | 6.668 | — | 0.333 | Работает |
| int4 | — | 6.695 | 0.304 | Работает (STE) |
| int8 | — | 6.903 | 0.096 | Работает |
| nf4 | 7.000 | 7.000 | **0.000** | **НЕ тренируется** (#217) |

## Связь с нашим GF16+

```
IGLA RACE использует:     gf256 (champion), gf16, fp8, int4, int8
Наш вклад (GF16+):        100% gradient survival (vs gf16's 64%)
                          Silicon proven: dot product 8.0 ✓
                          Golden Ruler: #1 recommendation for training

Что МЫ можем дать IGLA RACE:
  1. GF16+ → заменяет gf16 (exact Quire accumulation, 0 gradient loss)
  2. Golden Ruler → автоподбор формата под workload
  3. Format catalog (72/83) → расширить матрицу тестирования
  4. Coq invariants INV-3/INV-5 → формальная верификация GF16 safe domain
```

## Что нужно сделать (план)

1. **Клонировать trios-trainer-igla** → добавить GF16+ как формат
2. **Починить nf4 (#217)** → добавить scale + STE (похоже на наш fake_quant fix)
3. **Запустить GF16+ на IGLA RACE** → сравнить BPB с gf16
4. **Email Hunhold** → совместная статья с takum benchmark
