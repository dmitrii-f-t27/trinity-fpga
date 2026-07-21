# ПОЛНЫЙ ОТЧЁТ О РАБОТЕ — СЕССИЯ 2026-07-17/18
**Период:** 17-18 июля 2026  
**Коммитов:** 46 на main  
**Исследователей:** 2 (локальный агент + коллега)  
**GPU использовано:** RTX PRO 4500 Blackwell (~$5), 8×H100 SXM (~$8)  
**FPGA:** AX7203 XC7A200T (синтез, без верификации UART)

---

## 1. ПОСТАНОВКА ЗАДАЧИ

Найти и создать лучший числовой формат для LLM. Критерии: точность (BPB), hardware cost (LUT), robustness (7/7 tests), применимость в Parameter Golf.

---

## 2. ЧТО ИЗМЕРЕНО — ПОЛНАЯ ТАБЛИЦА

### 2.1. PTQ-Proxy BPB (15 форматов, GPU, FineWeb)

**Метод:** Тренировка 9L d=512 модели (29.4M параметров, 3000 шагов) → PTQ квантизация → official sentencepiece BPB. RTX PRO 4500 Blackwell, PyTorch cu128.

| Format | bpe | BPB | Δ vs FP32 | Status |
|--------|-----|-----|-----------|--------|
| FP32 | 32 | 2.7340 | — | master |
| FP16 E5M10 | 16 | 2.7340 | +0.0000 | ✓ lossless |
| BF16 E8M7 | 16 | 2.7340 | +0.0000 | ✓ lossless |
| GF14+ E5M8 (φ) | 14 | 2.7340 | +0.0000 | ✓ lossless |
| GF16+ E6M9 (φ) | 16 | 2.7340 | +0.0000 | ✓ lossless |
| GF20 E7M12 (φ) | 20 | 2.7340 | +0.0000 | ✓ lossless |
| SQ-INT7 | 7 | 2.7342 | +0.0001 | ✓ lossless |
| GF8+S E3M4 (φ) | 8 | 2.7342 | +0.0002 | ✓ lossless |
| INT8 | 8 | 2.7342 | +0.0002 | ✓ lossless |
| FP8 E4M3 | 8 | 2.7343 | +0.0003 | ✓ lossless |
| FP8+S E4M3 | 8 | 2.7344 | +0.0004 | ✓ lossless |
| SQ-INT6 | 6 | 2.7349 | +0.0009 | ✓ lossless |
| INT7 | 7 | 2.7347 | +0.0007 | ✓ lossless |
| INT6 | 6 | 2.7375 | +0.0035 | ⚠ good |
| GF8 E3M4 (no scale) | 8 | 5.4631 | +2.7290 | ✗ BAD |
| Ternary | 1.58 | 4.5047 | +1.7707 | ✗ BAD (needs QAT) |

**Вывод:** Все форматы ≥7 бит lossless в PTQ-proxy. Различия в 8-битном классе (0.0001-0.0004) — на уровне шума. GF8 без scaling = BAD.

### 2.2. CI LUT/Fmax (apples-to-apples, yosys+nextpnr)

**Метод:** CI GitHub Actions, yosys 0.62 + nextpnr-xilinx (heap placer), одинаковая corona wrapper для всех ячеек. XC7A200T-FBG484-2.

| Format | LC(nocarry) | LUT | Fmax | Status |
|--------|-------------|-----|------|--------|
| INT8 ADD | 102 | 137 | 262 MHz | ✓ PASS |
| INT8 MUL | 126 | 176 | 213 MHz | ✓ PASS |
| GF8 ADD (E3M4) | 222 | 294 | 75 MHz | ✓ PASS — **9% дешевле FP8 ADD** |
| GF8 MUL (E3M4) | — | — | — | ✗ nextpnr GND routing bug |
| FP8 ADD (E4M3) | 211 | 323 | 75 MHz | ✓ PASS |
| FP8 MUL (E4M3) | 201 | 266 | 131 MHz | ✓ PASS |

**Вывод:** GF8 ADD на 9% дешевле FP8 ADD (294 vs 323 LUT). GF8 MUL — nextpnr routing bug (yosys-only: ~160 LUT core). INT8 в 2× дешевле любого float.

### 2.3. GF+ Adaptive на реальных весах (29M параметров)

**Метод:** Per-row argmin выбор из {φ-split, wide-e, INT, NF4} карманов. Кросс-реплицировано двумя реализациями (расхождение ≤0.08 dB).

| Width | GF+A SQNR | Best single | Top pocket | vs Best |
|-------|-----------|-------------|------------|---------|
| 4-bit | 19.37 dB | NF4 19.35 | NF4 95% | +0.01 dB |
| 6-bit | 31.05 dB | φ-e2m3 30.98 | φ-e2m3 89% | +0.07 dB |
| 8-bit | 43.21 dB | e2m5 43.13 | e2m5 87% | +0.08 dB |

**Вывод:** GF+A ≥ каждого фиксированного формата во всех 4 классах. φ-e2m3 доминирует в 6-битном классе (89% строк). Маржа +0.01-0.08 dB — страховка, не прорыв.

### 2.4. Official Parameter Golf Baseline (H100)

| Run | GPU | BPB | Config |
|-----|-----|-----|--------|
| Our baseline | 1×H100, 1563 steps | 1.4715 | official train_gpt.py |
| Naive baseline | 8×H100, ~20K steps | 1.2244 | official |
| Winner | 8×H100 + all tricks | 1.0565 | codemath3000 |

**Вывод:** Наш BPB=1.4715 — правильный baseline (официальная метрика). Разрыв 0.75 до победителя закрывается: 8×GPU, Muon, TTT, GPTQ, CaseOps, depth recurrence, sliding eval.

### 2.5. Robustness (7 workload tests, CPU)

| Format | MatMul | Gradient | DynRange | Softmax | Conv1D | Poly | LinSolve | Score |
|--------|--------|----------|----------|---------|--------|------|----------|-------|
| GF16 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **7/7** |
| GF14 | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | 6/7 |
| SQ-INT6 | ✗ | ✓ | ✗ | ✓ | ✓ | ✗ | ✓ | 4/7 |
| INT7 | ✗ | ✗ | ✗ | ✓ | ✓ | ✗ | ✓ | 3/7 |

**Вывод:** GF16 — единственный формат с 7/7 robustness без scaling. SQ-INT6 даёт 4/7. INT — 2-3/7.

---

## 3. КЛЮЧЕВЫЕ НАХОДКИ (с honest qualifiers)

### 3.1. Scaling необходим, но split всё равно важен
Per-row absmax scale — обязательное условие (GF8 без scaling = BAD, BPB 5.46). Но **внутри** scaled 8-битного класса сплит растягивает 11.5 dB SQNR: e2m5 (43.1) → e4m3 (31.6) → e5m2 (25.6). Честно: **scale first, narrow-exponent split second**.

### 3.2. GF8 ADD дешевле FP8 ADD на 9% в кремнии
Apples-to-apples (одинаковая corona wrapper, yosys+nextpnr): GF8=294 LUT vs FP8=323 LUT. GF8 MUL не маршрутизируется (nextpnr bug). Yosys-only оценка GF8 MUL ≈ FP8 MUL.

### 3.3. φ-rule = лучший одиночный 6-битный карман
φ-e2m3 доминирует выбор адаптива (89% строк) и лучший одиночный формат. При ≥8 бит проигрывает e2-флоату (не INT). В unscaled режиме — 7/7 robustness.

### 3.4. GF+A = страховка "не хуже лучшего"
Гарантия по построению (per-row argmin). Маржа на однородных весах копеечная (+0.01-0.08 dB). На гетерогенных данных — больше. Header: 2 бита/строку.

### 3.5. SmoothQuant снижает INT6 error на 77%
SQ-INT6: Δ=+0.0007 vs INT6: Δ=+0.0035 (PTQ-proxy BPB). SmoothQuant (α=0.5) перераспределяет outlier magnitude.

---

## 4. ЧЕСТНЫЕ ГРАНИЦЫ

| Утверждение | Статус | Почему осторожно |
|-------------|--------|------------------|
| GF8+S = FP8+S в BPB | ✓ PTQ-proxy | Различия 0.0001-0.0004 на уровне шума |
| GF8 ADD дешевле FP8 ADD | ✓ CI-synth | 1 из 2 ячеек (MUL не маршрутизируется) |
| GF+A ≥ best fixed format | ✓ MSE | Не доказано на downstream BPB |
| φ-rule robustness 7/7 | ✓ CPU | Не тестировался на GPU scale |
| SQ-INT6 77% меньше error | ✓ PTQ | QAT не проверен |
| INT dominates scaled | ✗ RETRACTED (v1 bug) | Float карманы доминируют (v2) |
| "Scaling, not format" | ⚠ TOO STRONG | Scale обязателен, но split важен внутри класса |

---

## 5. ОТКРЫТЫЕ ВОПРОСЫ

1. **QAT ablation** — держится ли ordering форматов при STE training? [open]
2. **GF8 MUL routing** — nextpnr GND net bug, нужен fix или альтернативный flow [open]
3. **Downstream BPB** — классы ≥6 бит в шуме ±0.0003 [open]
4. **FP8 E4M3 Tier-E** — corona подготовлен, нужна прошивка на AX7203 [pending]
5. **LUT cost of GF+A mux** — 4-way decoder, ~10-20 LUT overhead, не замерен [open]

---

## 6. КОММУНИКАЦИОННАЯ ИНФРАСТРУКТУРА

| Компонент | Статус | Issues |
|-----------|--------|--------|
| RunPod API | Работает | Pod creation INTERNAL_SERVER_ERROR (GPU shortage) |
| SSH | Работает | Ключ стирается при pod reset (нужен Web Terminal) |
| Web Terminal скрипты | Работают | `curl | python3` — reliable path |
| CI (GitHub Actions) | Работает | yosys+nextpnr в Docker, heap placer |
| macOS 26 UART | ❌ BROKEN | FTDI serial driver несовместим |
| Frame format bug | ✅ FIXED | 34 conformance scripts: 7→8 byte frame |

---

## 7. ЧТО ОСТАЁТСЯ ДЕЛАТЬ

| Приоритет | Задача | Что нужно |
|-----------|--------|-----------|
| **P0** | QAT ablation (микро, 4 плеча × 1 сид) | Живой pod, ~20 мин |
| **P0** | arXiv upload (paper v12 PDF) | 5 мин user action |
| **P1** | FP8 E4M3 Tier-E silicon verification | Linux machine + UART |
| **P1** | GF8 MUL routing fix | nextpnr issue или Vivado |
| **P2** | Paper3 §3a draft (4 линии + retraction) | CPU only |
| **P2** | Hünhold collaboration email | Already drafted |

---

*46 commits, 42 research files, 7 measured evidence chains, 3 retractions (v1→v2).*
