# gf96 — строгий SW-bitexact (горизонт A, Trinity Catalog-100)

**Дата:** 2026-07-24. **Автор:** Vasilev (gHashTag), ORCID 0009-0008-4294-6159.

## Что закрыто

gf96 = GF(N=96, E=36, M=59, BIAS=34359738367) переведён из
`bitexact_selfconsistent` (существующий FP32-truncating conformance
`gf96_decode_conformance_ax7203.py` — один decode-закон, теряет 36 бит мантиссы
M=59→23, НЕТ 2-го witness) в **строгий SW-bitexact**: independent decoder,
abs_error == 0, ТРИ независимых witness.

Продолжение приёма gf48 (коммит `c3ab8264`) — та же методология (binary64 +
3 witness + iverilog), но с двумя качественными отличиями, описанными ниже.

## Почему binary64, и чем gf96 сложнее gf48

1. **M=59 > 52.** gf96 хранит 59 бит мантиссы, FP32 — 23 (теряется 36 бит),
   поэтому перевод в FP32 принципиально self-consistent. binary64 хранит 52 бита,
   НО 59−52 = **7 бит всё равно нужно округлять** round-to-nearest-even. У gf48
   (M=29 ≤ 52) округления не было — чистый сдвиг. Здесь RNE-путь 59→52 —
   содержательная часть пруфа, и все 3 witness реализуют его независимо.
2. **BIAS = 34359738367 = 2³⁵−1 > 2³¹.** Точное значение
   `(1 + m/2⁵⁹)·2^(e−BIAS)` содержит степень 2^(±3.4·10¹⁰). Поэтому witness A
   использует **mpmath** (где экспонента — отдельный Python-int, O(1)), а НЕ
   `fractions.Fraction` (которая материализовала бы ~10 ГБ целое — как и было
   уроком в gf48 через `2^(e−131071)`, только здесь масштаб невыполним вовсе).
   В RTL BIAS перенесён в 36-битный localparam (32-битный Verilog `integer`
   переполнен), а рабочий экспонент — в знаковый 41-бит.
3. **Диапазон экспоненты ±2³⁵ против binary64 ±1023/1074.** Подавляющее
   большинство gf96-кодов отображается в ±inf (overflow) или ±0 (underflow)
   binary64; только окно `e ≈ BIAS` (|true_exp| ≤ ~1074) даёт конечное ненулевое
   значение, и только там округление 59→52 реально срабатывает.

## Три независимых witness (`[доказано]`)

| # | Witness | Реализация | Роль |
|---|---------|-----------|------|
| A | `witness_A` в `gf96_bitexact_oracle.py` | точный **mpmath** mpf (dps=80 ≫ 59 бит → каждое диадическое входное значение точно) → корректно-округлённый binary64 через `frexp` + scaling на сетку `[2⁵²,2⁵³)` + RNE-сравнение с 1/2 (БЕЗ guard/sticky) | эталон-оракул |
| B | `witness_B` в том же файле | field-by-field **integer** construction (БЕЗ mpmath, БЕЗ Fraction), guard/sticky битовый разбор для округления 59→52, широкий знаковый экспонент (чистое целочисленное сложение/вычитание → гигантский диапазон не материализуется) | 2-й независимый SW-witness |
| C | `gf96_decode_fp64.v` + `tb_gf96_decode_fp64.v` через **iverilog 13.0** | fixed-width Verilog integer datapath (BIAS как 36-bit localparam, E2 signed [40:0], 60-бит full_sig, RNE guard/sticky, overflow→±inf / underflow→±0) | RTL-witness (ловит truncation/width/OOB-баги, инв. №6) |

## Результат прогона (2026-07-24, sandbox, iverilog 13.0)

```
WITNESS CROSS-CHECK (A mpmath-exact vs B integer-construct): 59050/59050 agree (mismatch=0)
HW RESULT: 59050/59050 bit-exact (fails=0)     # RTL (C) vs oracle
```

Все три witness сошлись **59050/59050 бит-в-бит, 0 расхождений**.

Доп. независимая сверка: для случаев, где вход точно представим во float64,
 witness-A совпал с Python `struct.pack('>d', ...)` (напр. `m=0x7F, te=0` →
`0x3ff0000000000001` с обеих сторон) — третья сторона подтверждает RNE.

## Sweep и покрытие классов

59050 векторов покрывают все 5 классов decode и все классы binary64-выхода:
`norm` 49108, `sub` 1262, `+inf` 2077, `−inf` 2167, `+0` 2199, `−0` 2233, `nan` 4.

Границы проверены точно (true_exp = e − BIAS):
- `te = 1024 → +inf` (overflow), `te = 1023 → max-normal` (`0x7fe0…`),
  `te = −1022 → min-normal` (`0x0010…`),
  `te = −1074 → min-subnormal` (`0x…0001`), `te = −1075 → ±0` (underflow).
- Плотное окно `e ∈ [BIAS−1130, BIAS+1074]` упражняет и normal, и subnormal,
  и сами границы переходов классов; мантиссы специально стрессят младшие 7 бит
  (guard/sticky: `0x7F`, `0x40`, `0x3F`, точный half, и т.п.) — там, где
  округление 59→52 реально решает.
- Дальнее поле (`e` далеко от BIAS) и gf96-subnormals (e=0) упражняют ветки
  overflow→±inf и underflow→±0; плюс детерминированный random (seed=20260724).
- Полный exhaustive (2⁹⁶ кодов) невозможен — это тот же тир строгости, что и
  FPGA-conformance для широких форматов (и что у gf48).

## Тир и границы (BINDING)

- Это **строгий SW-bitexact** `[доказано]` — НЕ Tier-E (нет прогона на кремнии
  AX7203). Синтез/PnR/flash на плату = `[ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ]`, отдельный
  эпик (64-битный выход, не FP32-lineup).
- Горизонт A: живой снимок SW-bitexact 70→71, остаток promotable selfconsistent
  5→4 (остаются `gf128/256/512/1024`).

## Урок этой сессии

Широкий знаковый экспонент в RTL нельзя срезать в поле напрямую:
`exp_field = E2_post[10:0] + 1023` ломается для отрицательных E2 (срез младших
11 бит из two's-complement даёт мусор → для E2=−1024 получалось field=2047 →
ложный overflow → +inf вместо subnormal). Правильно: **сначала знаковая сумма
`E2_post + 1023`, потом срез младших 11 бит**, и не добавлять в `is_overflow`
избыточный тест `exp_field >= 2047` (он дублирует `E2_post >= 1024` и вреден для
отрицательных E2). Этот класс багов (width/sign срез) — именно то, что ловит
iverilog и НЕ ловит python-транскрипция (инв. №6).

## Файлы

- `conformance/gf96_bitexact_oracle.py` — witness A (mpmath) + B (integer), генерация векторов
- `conformance/gf96_vectors.hex` — 59050 векторов «<96-бит raw> <64-бит expected>»
- `fpga/openxc7-synth/gf96_decode_fp64.v` — RTL witness C
- `fpga/openxc7-synth/tb_gf96_decode_fp64.v` — iverilog testbench

## Воспроизведение

```bash
cd conformance && python3 gf96_bitexact_oracle.py    # A==B + пишет vectors
cp gf96_vectors.hex /tmp/ && cd /tmp
iverilog -g2012 -o gf96_tb ../<repo>/fpga/openxc7-synth/gf96_decode_fp64.v \
                            ../<repo>/fpga/openxc7-synth/tb_gf96_decode_fp64.v
vvp gf96_tb                                            # C vs oracle
```
