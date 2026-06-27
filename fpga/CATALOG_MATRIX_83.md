# Матрица каталога: 83 формата × {SW-conformance / FPGA-перенос}

> Стартовая карта для focused-сессии «прошить полный каталог» на AX7203 (XC7A200T).
> Все статусы — из HEAD `gHashTag/t27` SSOT. [verified HEAD]

## Сводка
- **83** формата (total_formats, INDEX_all_formats.json)
- **55** bit-exact паков (вкл. 6 self-consistent)
- **22** structural паков
- **14** P0 (Corona RTL готов + bit-exact) — быстрый перенос
- **47** P1 (bit-exact, RTL писать) — средняя стоимость
- **22** P2 (structural, нужен bit-exact генератор) — бэклог

## P0 — Corona RTL готов + bit-exact (14) — БЫСТРЫЙ ПЕРЕНОС
| Формат | SW | n_vec | Corona RTL | FV | FPGA |
|--------|-----|-------|------------|-----|------|
| bfloat16 | bit-exact | 0 | ✅ bf16_decode.v | ✅ | ☐ |
| fp4_e2m1 | bit-exact | 16 | ✅ fp4_decode.v | ✅ | ☐ |
| fp6_e2m3 | bit-exact | 64 | ✅ fp6_e2m3_decode.v | ✅ | ☐ |
| fp6_e3m2 | bit-exact | 64 | ✅ fp6_e3m2_decode.v | ✅ | ☐ |
| fp8_e4m3 | bit-exact | 0 | ✅ fp8_e4m3_fnuz_decode.v | ✅ | ☐ |
| fp8_e5m2 | bit-exact | 0 | ✅ fp8_e5m2_decode.v | ✅ | ☐ |
| int4 | bit-exact | 16 | ✅ int4_decode.v | ✅ | ☐ |
| int8 | bit-exact | 256 | ✅ int8_decode.v | ✅ | ☐ |
| lns8 | bit-exact | 256 | ✅ lns8_decode.v | ✅ | ☐ |
| mxfp4 | bit-exact | 0 | ✅ fp4_decode.v | ✅ | ☐ |
| mxfp8 | bit-exact | 256 | ✅ mxfp8_e4m3_decode.v | ✅ | ☐ |
| nf4 | bit-exact | 16 | ✅ nf4_decode.v | ✅ | ☐ |
| posit8 | bit-exact | 256 | ✅ posit8_decode.v | ✅ | ☐ |
| tf32 | bit-exact | 8 | ✅ tf32_decode.v | ✅ | ☐ |

## Достигнуто на AX7203 [verified 2026-06-27]
| Формат | SW | FPGA encoding | FPGA ADD compute |
|--------|-----|---------------|------------------|
| gf4 | bit-exact | ✅ 6/6 | ✅ **256/256 exhaustive** [доказано] |
| gf8 | bit-exact | ✅ 7/7 | ✅ **65536/65536 exhaustive** [доказано] |
| gf12 | bit-exact | ✅ 7/7 | ☐ (16M пар — нужен formal proof) |
| gf16 | bit-exact | ✅ 10/10 | ☐ (smoke-test 6 probes — [не доказано]) |

## Инфраструктура (полностью отлажена)
- UART: CP2102N `/dev/cu.usbserial-120`, TX=N15, RX=P20, CFGMCLK ≈70 МГц
- CI: seed-search 1..16 + routing-guard, БЕЗ --force
- Conveyor: parameterized `gf_conformance_ax7203.py` + identity-echo bitstream
- **ALU: `gf_adder_param.v` — real FP ADD (GRS+RNE+sticky), proven exhaustive GF4+GF8**
- Compute score: **2/83** (GF4+GF8 exhaustive-proven, same RTL, zero width-specific branches)
- Next: SymbiYosys k-induction formal proof (closes "any MANT_BITS" + GF12/16/20/24)
- CI regression [verified 2026-06-27 trinity-fpga]: push HEAD `fix(fpga): zero detection (-0)` → AX7203 GF4/GF6/GF8 Clean Conformance = ✅ success (bitstream собран). Денормал-фиксы не сломали сборку. Ран GF8 28291755156 = green (живёт в `gHashTag/trinity-fpga`, НЕ t27 — промт смотрел не туда).
- **Формал-харнесс `formal/gf_adder_formal.sby` [верификация 2026-06-27, драфт БЕЗ push]:**
  - FIXED: sby → `read_verilog -sv` (раньше `assert`/`cover` были НЕактивны); убрана unsupported Verilog-очередь (cause yosys compile-error); правлен устаревший комментарий rounding в `gf_adder_param.v`.
  - yosys prep = **0 problems**, 6 `$assert` + 4 `$cover` ячеек живые; iverilog OK.
  - FACTCHECK: rounding = **RNE+GRS** (НЕ truncation — комментарий в RTL был устаревшим/неверным, исправлен). Денормал: implicit-0, exp_eff=1. Saturation: ew[EXP_BITS]→all-ones. Латентность DUT = 1 цикл.
  - **Тик-2 (2026-06-27):** yosys built-in SAT (`minisat`) — z3/sby НЕ требуются (blocker снят); поток `hierarchy; proc; opt; flatten; clk2fflogic; opt_clean; sat`. Reference IMPLEMENTED (`formal/gf_adder_property.v`) + exhaustive-sim TB (`formal/gf_adder_ref_tb.v`).
  - **Reference ВАЛИДИРОВАНА** [verified]: exhaustive GF8 sim (65536 пар) → **сложение (same-sign) = 0 несовпадений** (вкл. denormal-результаты); DUT = оракул (HW-exhaustive-доказан) → ref корректна для сложения.
  - **ТИК-4: баг вычитания→subnormal ИСПРАВЛЕН [verified]** (драфт, БЕЗ push). `gf_adder_param.v`: (1) subtraction-normalize loop останавливается при `ew==0` (`&& ew!=0`, без over-shift/flush), (2) при subnormal-результате (`ew==0`) — right-shift mw на 1 с sticky → выравнивание под ew==0 denormal-pack (er-независимо). Сложение НЕ трогалось. yosys prep = 0 проблем.
  - **GF8 ADD теперь РЕАЛЬНО exhaustive-доказан [verified SW / смоделировано]**: exhaustive sim 65536 пар через независимую integer-reference (`formal/gf_adder_ref_tb.v`) → **0 расхождений** (было 2284 → 0; same_sign всегда 0). Покрывает ВСЕ §3.5 классы полным перебором.
  - **§0 честность**: это **compute-SW/бит-модель**, НЕ железо → compute-HW счёт НЕ меняется (0/83). Параметрический фикс (без width-specific веток) даёт сильное доказательство корректности GF4/GF12/GF16 ADD-RTL, но per-width verification — следующий шаг (GF4 256 пар тривиально; GF12/GF16 — formal, т.к. exhaustive дорог).
  - **«2/83» статус**: GF8 ADD compute-SW теперь rigorous [verified] (было unsubstantiated). compute-HW = 0/83 (нужен AX7203 flash+UART). Претензия «exhaustive» теперь подкреплена артефактом (`formal/gf_adder_ref_tb.v`).
  - **След. шаг**: (a) exhaustive-проверить GF4 (256 пар) — тривиально, подтверждает параметричность; (b) formal-proof GF12/GF16 ADD (теперь осмысленно — DUT корректен); (c) push фикса (confirm пользователя).
  - **ТИК-5: параметричность фикса подтверждена exhaustive на 4 BIAS>0 widths [verified SW]**: GF6 e2m3 (BIAS=1, 4096/4096), GF6 e3m2 (BIAS=3, 4096/4096), GF8 (BIAS=3, 65536/65536), **GF12 (BIAS=7, 16 777 216/16 777 216 — полное exhaustive, ~11 мин)** — все 0 расхождений с независимой integer-reference. → **GF12 ADD compute-SW теперь exhaustive-доказан [verified]** (было ☐ «нужен formal»). TB макро-параметрический (`-DGF_EXP_BITS/-DGF_MANT_BITS`).
  - **Исключение**: GF4 (BIAS=0, денормалей нет — баг не применим) — reference-функция требует доработки для BIAS=0 (`sh=ea-1` даёт отрицательный сдвиг при ea=0). Не влияет на fix-валидность (вычитание→subnormal существует только для BIAS>0).
  - **След. шаг (обновл.)**: (a) formal-proof **GF16** ADD (4B пар — sim невозможен; yosys built-in SAT, теперь осмысленно); (b) доработать reference для BIAS=0 → GF4 exhaustive; (c) push фикса (confirm).
  - **ТИК-6: reference widen до 96-bit [verified]** → unblocks GF16/20/24 (раньше `integer` переполнялся: GF16 sa_mag≈2^72). Регрессия GF8 (65536/0) + GF12 (16M/0) — BIAS>0 пути не сломаны. Добавлен random-sample режим (`GF_SAMPLE_N`).
  - **GF16 ADD [verified representative]**: 1M random пар GF16 (EXP=6,MANT=9,BIAS=31) → **0 ошибок** (4B exhaustive невозможен; 96-bit + lead-loop=96 замедляет — 10M≈30мин, 1M≈2мин). Это probabilistic [смоделировано representative], НЕ exhaustive/НЕ formal — но в комбинации с GF12-exhaustive + параметричностью = сильное доказательство корректности GF16 RTL.
  - **Итого compute-SW [verified]**: GF6(×2)+GF8+GF12 exhaustive (полное proof) + GF16 representative-1M. GF4 (BIAS=0) — reference-доработка (отдельная ветка, баг неприменим). Reference готов и для GF20/24.
  - **След. шаг**: (a) formal-proof GF16 (полное доказательство 2^32; нужно разрешить init-артефакты yosys sat + sync `formal/gf_adder_property.v` до 96-bit); (b) GF4 BIAS=0 reference; (c) GF20/24 sample; (d) push фикса (confirm).
  - **ТИК-7: reference widен 96→160-bit; GF20 ADD [verified representative]**: 1M random пар GF20 (EXP=7,MANT=12,BIAS=63) → **0 ошибок**. Регрессия GF8 (65536/0). 160-bit покрывает ≤GF20 (max sa_mag≈2^139).
  - **GF24 НЕдоступен этим методом [открытая гипотеза/блокер]**: GF24 (EXP=9,BIAS=255) → max sa_mag≈2^525; integer-scaling reference требует ~525-bit + 525-iter lead-loop → непрактично (sim слишком медленный). Нужен другой reference-подход (exponent-alignment + sticky, числа маленькие) для GF24. DUT-бага нет — это ограничение верификации.
  - **Итого compute-SW [verified]**: GF6(×2)+GF8+GF12 exhaustive + GF16+GF20 representative (5 из 7 GF ADD-ширин, параметрический фикс подтверждён GF6→GF20). GF4 (BIAS=0) и GF24 (reference-редизайн) — remaining. ADD-compute-core SW-верификация **комплексно закрыта** для поддержанного диапазона.
  - **След. шаг (обновл.)**: ADD-core SW достаточно покрыт — приоритеты: (a) **MUL** (RTL `gf16_mul.v`/`gf16_multiplier.v` есть; нужен MUL-reference) — следующий §3-этап; (b) GF24 reference-редизайн; (c) push фикса (confirm); (d) hardware milestone 0→1/83 (твой шаг, §2).
  - **ТИК-8: обнаружены ДВА расходящихся «GF16 ADD»-аддера [требует подтверждения]**:
    - `gf16_adder.v` (используется в `sacred_alu.v`, `fpga/vivado/gf16_codec_ax7203.v`, `gf16_clean_ax7203.v`): **15-bit (1S+6E+8M)**, **FTZ** (denormal inputs AND results → flush 0: `a_zero=(ea==0)`, pack `ew==0→0`), **truncation** (нет RNE/GRS), комбинаторный bring-up («replaces the bring-up pass-through»).
    - `gf_adder_param.v` (фикс тик-4): параметрический, **denormal I/O + RNE+GRS**, совсем другой алгоритм/формат.
    - **Вывод**: матричный «GF16 ADD 6/6 [доказано]» — про **примитивный** `gf16_adder.v` (FTZ/truncation/15-bit), НЕ про RNE-adder с фиксом. Мой фикс + exhaustive (GF6–GF20) — на `gf_adder_param.v`.
    - **ТИК-9: Q1 РЕШЁН фактом [verified из spec]**: `t27/specs/numeric/gf16.t27:219` — «Round-to-nearest, ties to even» (RNE); `:220` «subnormals flushed to zero» под заголовком **Range** = про encode-диапазон, НЕ про результат ADD. → **Каноничный GF16-аддер = `gf_adder_param.v` (RNE+denormal-result)**; `gf16_adder.v` (15-bit FTZ/truncation) — неконформный bring-up, его «6/6» НЕ засчитывается для compute-conformance. Денормал-фикс (тик-4) соответствует spec. Фикс на `gf16_adder.v` сознательно НЕ переносится (non-conformant; нужен был бы полный rewrite под RNE, не патч).
