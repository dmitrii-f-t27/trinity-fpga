# Competitive Analysis — Trinity GoldenFloat (GF) vs alternative number formats

**Дата:** 2026-07-24. **Контекст:** позиционирование семейства Trinity-GF
(`gf8..gf1024`, параметрические E/M/BIAS, φ-biased taper, бит-точный decode
через 3-witness mpmath/integer/RTL, заявленный «Vasilev Floor» `LUT_ADD ≈ 1.63·W²`)
для статьи/arXiv. Ось конкуренции — **LUT на FPGA при фиксированной бит-точности**.

Источник данных о конкурентах: веб-исследование (arXiv, OCP, vendor-блоги) +
аудит репо (см. `research/PAPER_INTEGRITY_ISSUES.md`).

---

## 1. Карта конкурентов

| Формат | Год | Идея | FPGA LUT-evidence | Главная слабость |
|--------|-----|------|-------------------|------------------|
| **Posit** | 2017/std 2022 | variable regime bits, taper near ±1 | **2–4× FP32 LUT** (add ≈0.9–2.5k, mul ≈1.1–2.7k LUT на Xilinx 7, PACGen/Chaurasiya) | regime decode (LZD+barrel-shift) доминирует; потери кодирования вдали от ±1; переменная латентность |
| **Takum** | 2024 (CoNGA) | logarithmic tapered, фикс dynamic-range-collapse posit'а | **НЕТ опубликованных FPGA LUT** (только `libtakum` C99) | нет silicon/FPGA; log-датапат тяжёлый; adoption ≈0 |
| **OCP MX (MXFP4/8/6)** | 2023 | block-shared E8M0 exponent per k=32 | ASIC tensor cores (Blackwell), **не LUT-axis** | block-granularity scale; не standalone scalar тип; FPGA-враждебный гетерогенный датапат |
| **NVIDIA FP8** (E4M3/E5M2) | 2022 | два 8-битных кодирования (fwd/bwd) | H100 tensor cores (ASIC), на FPGA mul всё равно дорогой (IEEE Xplore 11008970) | dual-encoding удваивает toolchain; E4M3 жертвует диапазоном, E5M2 — точностью |
| **bfloat16/8** | 2017 (Google) | FP32 exponent + урезанная мантисса | тривиальный convert в FP32, **минимальная своя логика** | тупой range-cut; низкая точность near ±1 (зря тратит биты без taper) |

**Развернуть позицию Trinity-GF:** конкуренты распадаются на
*(a) ASIC-tuned block-форматы* (MX, FP8, BF16 — низкая LUT-релевантность) и
*(b) tapered scalar форматы* (Posit, Takum — высокий LUT-cost, слабая FPGA-evidence).
**Окно Trinity-GF** = fixed-width taper + бит-точный decode + `1.63·W²` LUT-цель —
не закрыто ни одним лагерем.

## 2. Главный соперник на FPGA — Posit

Posit32 на FPGA = **2–4× от IEEE FP32 LUT** для add/mul (FP32 mul мапится на DSP,
posit — нет). Это прямое сравнение: Trinity-GF заявляет **sub-posit** ADD-цель
(`1.63·W²`). Чтобы статья была убедительной, нужно в одном месте, на одном
тулинге (openXC7/yosys), **при одинаковой бит-точности**, сравнить
`GF16/GF24 ADD/MUL LUT` vs `posit16/posit24 ADD/MUL LUT` и показать зазор.
Это **эксперимент №1 недостающего пруфа** (см. варианты усиления статьи ниже).

## 3. Takum — приоритет «опередить публикационно»

Takum (2024) — единственный competitor, который:
- прямо критикует Posit за dynamic-range-collapse (как и Trinity),
- НО не имеет **никакой** FPGA/LUT-evidence.

Trinity-GF уже имеет decode-RTL + bit-exact witnesses — то, чего у takum нет.
=> Стратегия: явно противопоставить в Related Work («takum решает ту же
проблему диапазона, но без hardware-доказательства; мы даём bit-exact decode
на 3-witness + LUT-floor»). Это сильный дифференциатор для рецензента.

## 4. Поддерживающая литература (оправдание LUT-оси)

- **LUTMUL** (FPGA 2025, ACM 10.1145/3658617.3697687): LUT на FPGA превосходят
  DSP ~100× → LUT-native multipliers бьют DSP-roofline. **Оправдывает выбор
  LUT как главной метрики для Trinity-GF.**
- **8-bit Transformer inference on edge** (Yu/Prabhu): posit8 и FP8 оба
  достигают BF16-точности при меньшей area/power.
- **FPGA Approximate Multiplier for FP8** (IEEE Xplore 11008970, 2024): dense
  FP8 mul дорог на FPGA → аппроксимации нужны — валидирует, что GF решает
  реальную боль.

## 5. Честные оговорки для статьи (из аудита репо)

Эти пункты нужно либо закрыть экспериментом, либо явно дисклеймить — иначе
рецензент их найдёт:

1. **Все LUT-числа — yosys pre-P&R**, нет committed nextpnr `.rpt`. Это уже
   дисклеймится в Threats to Validity (`paper.tex:1236`), но усиление возможно
   одним nextpnr-прогоном (вариант B ниже).
2. **GF64 НЕ бит-точен на silicon** (359/512 = 70.1%, `paper.tex:378`). Абстракт
   говорит «Ten GoldenFloat formats … 0 failures on silicon» — нужно явно
   ограничить «bit-exact» форматами ≤ GF32, а GF64 назвать «best-effort».
3. **Сэмплы 64–512 векторов** на silicon — маленькие. Абстракт звучит как
   exhaustive; нужно уточнить «representative sweep, 64–512 samples».
4. **takum16 MUL = 505 LUT заявлен в `paper.tex:337` без committed `takum16_mul.v`**
   (README:104 говорит «only takum16_decode.v exists»). Это **критический** пробел —
   claim без артефакта. Либо закоммитить RTL, либо убрать claim.

Полный список противоречий статьи — в `research/PAPER_INTEGRITY_ISSUES.md`.
