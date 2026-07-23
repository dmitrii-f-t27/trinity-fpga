# gf48 — строгий SW-bitexact (горизонт A, Trinity Catalog-100)

**Дата:** 2026-07-23. **Автор:** Vasilev (gHashTag), ORCID 0009-0008-4294-6159.

## Что закрыто

gf48 = GF(N=48, E=18, M=29, BIAS=131071) переведён из
`bitexact_selfconsistent` (существующий FP32-truncating conformance
`gf48_decode_conformance_ax7203.py` — один decode-закон, теряет 6 бит мантиссы
M=29→23, НЕТ 2-го witness) в **строгий SW-bitexact**: independent decoder,
abs_error == 0, ТРИ независимых witness.

## Почему binary64, а не binary32

gf48 имеет M=29 бит мантиссы. FP32 хранит только 23 → любой перевод gf48→FP32
ТРУНКИРУЕТ 6 бит, поэтому может быть только self-consistent, никогда строго
bit-exact против точного оракула. binary64 хранит 52 бита ≥ 29 → каждое конечное
*нормальное* значение gf48 представляется в binary64 с НУЛЕВЫМ округлением, что
делает сравнение abs_error==0 корректным.

## Три независимых witness (`[доказано]`)

| # | Witness | Реализация | Роль |
|---|---------|-----------|------|
| A | `witness_A` в `gf48_bitexact_oracle.py` | точный `fractions.Fraction` → корректно-округлённый binary64 (RNE в арбитрарной точности, `_floor_log2_frac` через bit_length, без float до финального шага) | эталон-оракул |
| B | `witness_B` в том же файле | field-by-field integer construction (БЕЗ Fraction, зеркалит RTL-датапат) | 2-й независимый SW-witness |
| C | `gf48_decode_fp64.v` + `tb_gf48_decode_fp64.v` через **iverilog 12.0** | fixed-width Verilog integer datapath | RTL-witness (ловит truncation/OOB-баги, инв. №6) |

## Результат прогона (2026-07-23, sandbox, iverilog 12.0)

```
WITNESS CROSS-CHECK (A exact-Fraction vs B integer-construct): 9616/9616 agree (mismatch=0)
HW RESULT: 9616/9616 bit-exact (fails=0)     # RTL (C) vs oracle
```

Все три witness сошлись **9616/9616 бит-в-бит, 0 расхождений**.

## Тир и границы (BINDING)

- Это **строгий SW-bitexact** `[доказано]` — НЕ Tier-E (нет прогона на кремнии
  AX7203). Синтез/PnR/flash на плату = `[ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ]`, отдельный
  эпик (64-битный выход, не FP32-lineup).
- Sweep = representative + boundary (граница fp64 normal/subnormal e≈BIAS−1022) +
  логарифмический разброс по всему диапазону экспонент + детерминированный
  random (seed=20260723). Полный exhaustive (2^48 кодов) невозможен — это тот же
  тир строгости, что и FPGA-conformance для широких форматов.
- Оракул A использует `_floor_log2_frac` через `bit_length` — БЕЗ итеративного
  умножения (иначе huge-power Fraction 2^(e−131071) взрывается на миллион-битных
  целых; урок этой сессии).

## Файлы

- `conformance/gf48_bitexact_oracle.py` — witness A + B, генерация векторов
- `conformance/gf48_vectors.hex` — 9616 векторов «<48-бит raw> <64-бит expected>»
- `fpga/openxc7-synth/gf48_decode_fp64.v` — RTL witness C
- `fpga/openxc7-synth/tb_gf48_decode_fp64.v` — iverilog testbench

## Воспроизведение

```bash
cd conformance && python3 gf48_bitexact_oracle.py    # A==B + пишет vectors
cp gf48_vectors.hex /tmp/ && cd /tmp
iverilog -g2012 -o gf48_tb ../<repo>/fpga/openxc7-synth/gf48_decode_fp64.v \
                            ../<repo>/fpga/openxc7-synth/tb_gf48_decode_fp64.v
vvp gf48_tb                                            # C vs oracle
```
