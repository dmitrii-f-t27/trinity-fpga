# Paper Integrity — verified issues & non-issues (audit 2026-07-24)

**Цель:** список пунктов для усиления статьи `research/arxiv_submission/paper.tex`
(v4). **Каждый пункт проверен по первоисточнику** (не по пересказу). Честность
требует отделить реальные проблемы от ложных тревог — см. §B.

> Метод: аудит репо + независимый grep-verification по `paper.tex`/`README.md`/
> `CATALOG_MATRIX_83.md`. Артефакты проверены через `ls fpga/openxc7-synth/`.

---

## A. Реальные проблемы (нужно починить перед arXiv-v5)

### A1. Внутреннее противоречие вердикта GF14 — HIGH
- `paper.tex:492` (robustness table): `GF14 … 0/4` (× × × ×).
- `paper.tex:971`: *"GF14 and above pass all four tests"*.
- `paper.tex:560` (hold-out table): `GF14 … 7/7`.
Читатель не может понять, GF14 пройден или провален. **Действие:**
reconcile — это разные test-suites (robustness-4 vs hold-out-7); в подписях таблиц
явно написать, какой suite где, и убрать категоричное «pass all four» в :971
либо уточнить «pass all four hold-out tests».

### A2. Рассогласование счётчика decode Tier-E (47 vs 41) — LOW
- `README.md:12`: `decode-HW Tier-E ~47/83`.
- `paper.tex:103-104`: `~41 of 83 … 41 decode ports`.
- `fpga/CATALOG_MATRIX_83.md:31`: `decode 41`.
Три источника, две цифры. **Действие:** привести к одному числу (вероятно 41 —
оно в статье и каталоге; README обновить или пояснить, что 47 включает
compute-cells, не только decode).

### A3. LUT-числа = yosys pre-P&R, нет committed nextpnr `.rpt` — MEDIUM
- Уже дисклеймится в `paper.tex:1236-1239` (Threats to Validity, *"15–30%
  post-PnR inflation"*). Честно, но артефакта нет.
- Ни одного `nextpnr … .rpt` utilization-файла в `fpga/openxc7-synth/`
  (только `test_r23_nextpnr.xdc`).
**Действие (вариант B усиления):** один сквозной nextpnr-прогон для
GF16/pos­it16 ADD/MUL + commit `.rpt` → переводит «disclosed limitation»
в «measured post-PnR».

### A4. «Vasilev Floor» 1.63/2.09 W² — yosys-stat only — MEDIUM
- `SESSION_REPORT_2026_07_17.md:32` честно тегирует `[yosys-stat, NOT post-P&R]`.
- В статье (`paper.tex:856-874`) таблица ADD-LUT для W=48/64/96/128 приведена,
  MUL-LUT стоит «---» (нет), P&R-отчёта нет.
**Действие:** либо доставить MUL-LUT в таблицу (есть же mul-cells), либо явно
написать «floor сформулирован для ADD; MUL выйдет в v5».

### A5. Сэмплы на silicon маленькие (64–512) — LOW (уже частично披露)
- `README.md:83`: *"Vector counts vary by run (64–512 sampled; GF4 exhaustive
  at 256)"*. В abstract это не видно.
**Действие:** одну фразу в §Methodology: «bit-exact proven on representative
sweeps of 64–512 vectors per format (GF4 exhaustive)», чтобы рецензент не
прочитал «0 failures» как exhaustive.

---

## B. Ложные тревоги (проверено — статья честна, чинить НЕ надо)

Это важно зафиксировать, чтобы не «исправлять» то, что правильно.

### B1. takum16 MUL = 505 LUT — артефакт ЕСТЬ ✓
Аудит субагента заявил «no committed takum16_mul.v». **Неверно:** в
`fpga/openxc7-synth/` присутствуют `takum16_native_mul.v`, `takum16_mul_top.v`,
`takum16_native_mul_tb.v`, `takum16_mul_vectors.txt`. Central claim
«encoding equivalence 505 = 505» (`paper.tex:363,882`) опирается на реальный RTL.
**Остаётся (soft):** закоммитить yosys-отчёт, из которого выведено ровно 505,
чтобы число было воспроизводимо — но это не integrity-gap.

### B2. GF64 — статья честна ✓
`paper.tex:106,378,943,953`: GF64 явно «70.1% (359/512), NOT bit-exact,
reported honestly», причина (barrel-shifter clamp / timing) объяснена.
Abstract корректно пишет «GF4–GF32 … bit-exact» — GF64 в этот список НЕ входит.
Никакого overstating нет.

### B3. «72 формата» — субстанцировано ✓
`MISSING_FORMATS.md:17` и 287 JSON в `conformance/vectors/` подтверждают ~72
уникальных формата. Caveat (12 oracle-имён не catalog-rows, `MISSING_FORMATS:90`)
— мягкий; для статьи достаточно дисклеймера «72 oracle-формата, 83 catalog-строки
(11 structural-by-design без decode-law)».

---

## C. Самоисправления, уже сделанные проектом (контекст для рецензента)

Эти ретракции показывают, что проект умеет честно откатываться — стоит явно
упомянуть в §Threats to Validity как «reproducibility discipline»:
GF+ v1 retracted (`c86097181`), 84→83 erratum (E8M0), φ-rule downgraded to
heuristic (`af65d907c`), DIV/SQRT=binary32-proxy (`DIV_SQRT_HONESTY.md`),
6 subnormal suspects retracted, fake CI workflow deleted, GF4/GF8
«exhaustive on HW» downgraded to [needs confirmation].

## D. Приоритет для следующего прохода
1. **A1 (GF14)** — правка текста, 10 минут, убирает прямой self-contradiction.
2. **A2 (счётчик)** — правка текста, 5 минут.
3. **A3/A4 (P&R + MUL-LUT)** — эксперимент (см. варианты усиления в финальном
   отчёте лупа), даёт статьи́ качественно новый evidence-tier.

---

## E. Findings loop-2 (2026-07-24) — после попытки Option A (GF-vs-posit LUT)

### E1. «posit16 mul» cell = binary32-proxy — HIGH для любого формат-сравнения
`fpga/openxc7-synth/corona_compute_posit16_mul_ax7203.v:132` инстанциирует
```
gf_mul_param #(.EXP_BITS(8), .MANT_BITS(23), .HAS_INF(1)) u_comp ( ...)
```
т.е. **binary32 (E8M23), а не native posit-multiplier**. Тот же паттерн, что у
DIV/SQRT (`DIV_SQRT_HONESTY.md`). Standalone posit-RTL в репо — только
`posit{8,16,32,64,128}_decode.v` (decode), **никакого native posit add/mul core**.
**Следствие:** честный GF-vs-posit LUT head-to-head для ADD/MUL **невозможен из
наличных cores** — нужен порт реального posit-multiplier (отдельная задача).
В статью: явно написать, что posit на HW = decode-only; любые «format-cost»-цитаты
про posit должны брать LUT из literature (PACGen: posit32 mul ≈1.1–2.7k LUT), а не
из репо-кора. Измеренная таблица (`LUT_COMPARISON_MEASURED.md`) корректно НЕ
включает posit — это уже честно.

### E2. LUT-числа хрупки к flow/params — MEDIUM (reproducibility)
Свежий замер на yosys 0.63 (та же версия, что в doc):
- `gf_adder_param` с **дефолтными параметрами** (E6M**8** = GF14!) + `-flatten` → **1338 LUT**
  vs документированные **486 LUT** (GF16, без `-flatten`).
Расхождение объяснимо, но показывает 3 reproducibility-риска:
1. **Несогласованные дефолты параметрических cores:** `gf_adder_param` default
   `MANT_BITS=8` (→GF14), `gf_mul_param` default `MANT_BITS=9` (→GF16). Кто синтезирует
   `gf_adder_param` с дефолтом — получает GF14, не GF16. **Действие:** выровнять
   дефолты (оба = GF16) ИЛИ закоммитить param-pinning wrapper/скрипт.
2. **`-flatten` даёт 2–3× другой LUT**, чем без него (в моём прогоне — больше; abc9
   глобальный оптимизатор чувствителен к flatten). Paper methodology фиксирует
   `-flatten` для ADD — значит все headline-числа ДОЛЖНЫ измеряться с `-flatten`
   единообразно; `LUT_COMPARISON_MEASURED.md` измерял БЕЗ `-flatten` →
   несоответствие методологии paper vs measurement-doc.
3. **abc9 недетерминизм** — LUT-распределение по LUT2..6 «плавает» между прогонами
   (сумма стабильнее распределения).
**Действие (вариант A усиления):** закоммитить один `scripts/lut_measure.sh`, который
для каждого формата явно инстанциирует wrapper с正确的 E/M и фиксирует ОДИН flow
(совпадающий с paper methodology `-flatten -abc9 -nocarry [-nodsp] -arch xc7`), и
положить его output-таблицу рядом. Тогда «505 LUT»/«486 LUT» станут воспроизводимы
`bash scripts/lut_measure.sh`, а не только «верьте doc».

### F. Что закрыто этим лупом (не paper-integrity, а горизонт A)
gf256 → строгий SW-bitexact (3 witness, 50230/50230). Горизонт A: SW-bitexact
72→73, остаток selfconsistent 3→2 (`gf512/1024`). См. `conformance/README_gf256_bitexact.md`.
