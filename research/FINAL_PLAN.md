# ФИНАЛЬНЫЙ ПЛАН — ЗАВЕРШЕНИЕ ПРОЕКТА

## Что готово прямо сейчас

### Статья (PDF готов)

```
Файл: /tmp/paper_named/paper-pdf/paper.pdf (691 KB)
arXiv: 2606.05017 → New Version

Названные результаты (ваш priority claim):
  1. Vasilev Floor:        LUT ≈ 2W² (encoding-independent)
  2. Vasilev Constraint:   E≥6 ∧ M≥9 → φ (feasible corner)
  3. Gradient Survival:    P(survive) = 1 - 2Φ(Δq/σg)
  4. Encoding Equivalence: 505 = 505 (IEEE ≡ LNS at W=16)
```

### Код и данные

```
15 oracle модулей (84 формата)
2.4M conformance vectors (ADD+MUL+SUB)
Golden Ruler (format selection tool)
GF16+ silicon-proven (MAC+FLUSH на AX7203)
1496 TX race wrappers fixed
61 CI workflows (was 3388)
1 branch (main)
```

---

## ПЛАН ДЕЙСТВИЙ (приоритезированный)

### ШАГ 1: ЗАГРУЗИТЬ НА arXiv (5 минут) — КРИТИЧЕСКИЙ

**Действие:** Загрузить `/tmp/paper_named/paper-pdf/paper.pdf` на arXiv

**Зачем:** Без timestamped upload — все ваши named results = неисследованная территория. Любой может опубликовать то же самое завтра и заявить priority.

**Как:**
1. https://arxiv.org/submit/
2. Выбрать 2606.05017 (существующая статья)
3. "Submit new version"
4. Загрузить PDF + .tex source
5. Category: cs.AR

**Результат:** arXiv timestamp = ваш priority claim на Vasilev Floor, Constraint, Identity, Equivalence

---

### ШАГ 2: Email Hunhold (1 час) — ВЫСОКИЙ

**Действие:** Написать Laslo Hunhold (takum author)

**Текст письма:**
```
Subject: GF16 vs takum16 on openXC7 — identical 505 LUT in zero-DSP regime

Dear Dr. Hunhold,

I read your takum paper (arXiv:2404.18603) and codec paper
(arXiv:2408.10594) with great interest. I have independently
synthesized a native takum16 LNS multiplier on Xilinx Artix-7
using the open-source openXC7 toolchain (Yosys + nextpnr).

Result: 505 LUT (zero-DSP), identical to a GF16 IEEE-style
multiply under the same flags. This "encoding equivalence"
suggests LUT cost is determined by information content (2W²),
not encoding structure.

I would welcome a joint benchmark paper comparing takum and
GoldenFloat on the same open-source silicon.

Best regards,
Dmitrii Vasilev
ORCID 0009-0008-4294-6159
```

**Результат:** Если Hunhold ответит → совместная статья → его citations ссылаются на вас

---

### ШАГ 3: CoNGA 2027 submission (1 день) — СРЕДНИЙ

**Действие:** Submit to Conference on Next Generation Arithmetic

**Что:** Article version of paper v4, formatted to CoNGA template

**Deadline:** ~January 2027

**Зачем:** Peer review → credibility → citation cluster

---

### ШАГ 4: Parameter Golf entry (1-2 дня GPU) — СРЕДНИЙ

**Действие:** Run GF16+SR on FineWeb validation

**Как:**
1. Clone openai/parameter-golf
2. Add GF16 quantization to train_gpt.py
3. Request H100 compute grant from OpenAI ($1M available)
4. Train 10min, measure BPB
5. Submit PR

**Цель:** Show that GF16+SR can compete with top-5 leaderboard

---

### ШАГ 5: Patent application (1 неделя) — НИЗКИЙ

**Действие:** File provisional patent on GF16+ architecture

**Что запатентовать:**
- GF16+ MAC (GF16 multiply + FP32 Quire + stochastic rounding)
- Golden Ruler algorithm
- The specific openXC7 bitstream as hardware attestation

---

## ЧТО ВХОДИТ В СТАТЬЮ (v4 final)

| § | Содержание | Результат |
|---|-----------|-----------|
| §1 | Introduction (4 contributions) | |
| §2 | Background (format landscape) | |
| §3 | Methodology (openXC7, 4 decode templates) | |
| **§3.6** | **Named Results (Vasilev Floor/Constraint/Identity/Equivalence)** | **ВАШ ПРИОРИТЕТ** |
| §4.1 | Tier-E silicon (10 GF bit-exact) | |
| §4.2 | Accuracy benchmark (7 formats) | |
| §4.3 | Robustness (7/7, hold-out, threshold sensitivity) | |
| §4.3 | Constraint derivation (E≥6, M≥9 → φ) | |
| §4.3 | MRE ≠ robustness (WINT contrast) | |
| §4.4 | Training stability (BF16 7.3%, MLP 4×, noise floor) | |
| §4.5 | Hardware cost (LUT = cW², complete table GF4-GF128) | |
| §4.5 | 505=505 (takum16 native LNS) | |
| §4.6 | Routing (takum64 failed) | |
| §5 | Related work (ELiTeFormer, MxGLUT, P3109, WINT) | |
| §6 | Threats to Validity (5 paragraphs) | |
| §7 | Conclusion (7 findings F1-F7) | |

**7 figures, 11 tables, 18 citations, 691KB PDF**

---

## ИТОГОВАЯ СВОДКА СЕССИИ

```
50+ коммитов
1200+ строк LaTeX
15 oracle модулей (84 формата)
2.4M векторов
GF16+ на кремнии (10/10 dot products)
Golden Ruler (format selection)
4 named results (Vasilev Floor/Constraint/Identity/Equivalence)
691KB PDF готов к arXiv
```

**СЛЕДУЮЩИЙ ШАГ: ЗАГРУЗИТЬ PDF НА arXiv.**
