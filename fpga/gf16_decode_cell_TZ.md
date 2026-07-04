# ТЗ: gf16-decode cell (чистый decode-only head-to-head для ARITH)

**Зачем:** matched-substrate квартет ([#233](https://github.com/gHashTag/trinity-fpga/issues/233)) сейчас сравнивает gf16 как **ADD-compute** (512/512) против posit16/takum16/binary16 как **decode**. Это не apples-to-apples. Рецензент ARITH ([#4](https://github.com/gHashTag/arith2027-goldenfloat/issues/4)) спросит именно про это. Отдельная gf16-**decode** ячейка ставит все 4 формата в одну операцию (decode→FP32).

**Статус актива:** cell НЕ существует. Весь gf16-RTL — compute (`gf16_add.v`, `gf16_mul.v`, `gf16_alu.v`, `gf16_mac_16.v`). Нет `gf16_decode.v`/`corona_decode_gf16`, нет в FMT-списке corona-decode-host, нет CI-workflow. Это **fresh design-loop**, не flash-сессия.

## Параметры формата (из SSOT `formats_catalog.t27`, [Verified])
- gf16: **bits=16, s=1, e=6, m=9, bias=31** (PHI_BIAS=60), storage=u16, cluster=GoldenFloat.
- FPGA-артефакт компонента: 35/35 @ 323 МГц Artix-7 (Zenodo 10.5281/zenodo.19227877).

## RTL-spec (gf16_decode.v: gf16 u16 → binary32)
Комбинационный декодер, зеркало decode-закона gf16 (тот же, что использует golden-оракул conformance):
1. Разбор поля: `s = bits[15]`, `e = bits[14:9]` (6 бит), `m = bits[8:0]` (9 бит).
2. Классы (5, как в §3.5 денормал-методологии): normal / subnormal (e=0) / zero / Inf / NaN (HAS_INF-семантика gf16).
3. Normal: `value = (-1)^s * 2^(e-bias) * (1 + m/2^9)`, bias=31 → эксп-диапазон и сдвиг мантиссы в FP32 (8 эксп / 23 мантисса), rebias 31→127.
4. Subnormal (e=0, m≠0): `value = (-1)^s * 2^(1-bias) * (m/2^9)` — нормализация в FP32 (leading-zero count по 9-битной мантиссе, коррекция экспоненты).
5. Zero/Inf/NaN → соответствующие FP32-паттерны.
6. Выход: `fp32[31:0]` (IEEE binary32), полностью комбинационно (или 1-такт регистр на выход для Fmax).

## Что написать (design-loop, НЕ этой сессией)
- [ ] `fpga/openxc7-synth/gf16_decode.v` (~50-100 строк) + опц. регистр выхода.
- [ ] Testbench: golden-оракул (Python decode gf16→fp32) == RTL в симуляции; классы normal/subnormal/zero/inf/nan.
- [ ] XDC под AX7203 (клок 200 МГц LVDS R4/T4 → IBUFDS; UART @160000).
- [ ] Добавить gf16 в FMT-список corona-decode-host + fmt-код.
- [ ] CI-workflow (по образцу corona-decode-*): synth (openXC7 Yosys+nextpnr) → битстрим-артефакт.
- [ ] Conformance-вектор: 64-vec (как у квартета) или exhaustive-подмножество для apples-to-apples.

## Критерии готовности (Tier-E chain 4/4)
- CI run GREEN URL + bitstream SHA256 + UART `HW RESULT: N/N bit-exact (fails=0)` @160000 + IDCODE live `0x13636093`.
- Результат: [измерено на FPGA], decode-only.
- Прикрепить к квартету на [#233](https://github.com/gHashTag/trinity-fpga/issues/233): теперь все 4 формата в одной операции (decode) → cost-spread строго сопоставим.

## Оценка LUT (грубая, [смоделировано])
Decode gf16→fp32 ≈ разбор + LZC(9) + rebias + мультиплексоры классов. Ориентир по соседним corona-decode ячейкам: десятки–~150 LC (для сравнения: binary16-decode=131 LC, posit16-decode=175 LC). Точное число даст synth.

## Honesty (binding)
- Никаких «первый/лучший». gf16-decode ≠ gf16-compute — это разные ячейки, обе честно тегировать.
- Пока cell не прошит на кремнии — статус [ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ] (synth+flash вне песочницы).
- 1-ULP subnormal residuals (если появятся) = KNOWN_LIMITATION, не hard-fail.

*Параметры gf16 сверены с живым SSOT 2026-07-04. Это ТЗ на следующий design-loop, не результат этой сессии.*
