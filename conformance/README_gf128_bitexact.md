# gf128 — строгий SW-bitexact (горизонт A, Trinity Catalog-100)

**Дата:** 2026-07-24. **Автор:** Vasilev (gHashTag), ORCID 0009-0008-4294-6159.

## Что закрыто

gf128 = GF(N=128, E=49, M=78, BIAS=281474976710655 = 2⁴⁸−1) переведён из
`bitexact_selfconsistent` (FP32-truncating conformance, теряет 55 бит мантиссы
M=78→23, один decode-закон) в **строгий SW-bitexact**: 3 независимых witness.

Продолжение gf48/gf96 (коммиты `c3ab8264`, `1a7fde6c`), самая «широкая» реализация
приёма: M=78 → округлять **26 бит** (gf96 округлял 7, gf48 — 0).

## Три независимых witness (`[доказано]`)

| # | Witness | Реализация |
|---|---------|-----------|
| A | `witness_A` | точный **mpmath** mpf (dps=100 ≫ 78 бит) → `frexp`+scaling+RNE half-cmp |
| B | `witness_B` | pure **integer** field-construct, guard/sticky для 78→52, экспонент как целое (±2⁴⁸ не материализуется) |
| C | `gf128_decode_fp64.v` | fixed-width Verilog, BIAS 48-bit localparam, E2 signed [55:0], 79-bit full_sig, iverilog 13.0 |

```
WITNESS CROSS-CHECK (A mpmath-exact vs B integer-construct): 54640/54640 agree (mismatch=0)
HW RESULT: 54640/54640 bit-exact (fails=0)     # RTL (C) vs oracle
```

Доп. сверка: `m=0x3FFFFFF, te=0` → A совпал с `struct.pack` (0x3ff0000000000001).
Покрытие классов: norm 45016, sub 1156, +inf 2082, −inf 2057, +0 2075, −0 2250, nan 4.
Границы `te=±1024/−1074` проверены точно.

## Урок, применённый с первого прогона

Урок gf96 (знаковый экспонент нельзя срезать в поле до сложения:
`E2_post[10:0]+1023` → ложный overflow на отрицательных E2) применён здесь
**сразу** — `exp_field = (E2_post + 1023)` как signed, потом `[10:0]`. Поэтому
gf128-RTL сошёлся 54640/54640 **без итерации багфикса** (gf96 потребовал 1 цикл).

## Тир и границы (BINDING)

- **Строгий SW-bitexact** `[доказано]` — НЕ Tier-E (нет прогона на AX7203).
  Синтез/PnR/flash = `[ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ]` (64-бит decode-кандидат).
- Горизонт A: SW-bitexact 71→72, остаток promotable selfconsistent 4→3
  (остаются `gf256/512/1024`).

## Файлы

- `conformance/gf128_bitexact_oracle.py` — witness A + B
- `conformance/gf128_vectors.hex` — 54640 векторов «<128-bit raw> <64-bit expected>»
- `fpga/openxc7-synth/gf128_decode_fp64.v` — RTL witness C
- `fpga/openxc7-synth/tb_gf128_decode_fp64.v` — iverilog testbench

## Воспроизведение

```bash
cd conformance && python3 gf128_bitexact_oracle.py
cp gf128_vectors.hex /tmp/ && cd /tmp
iverilog -g2012 -o gf128_tb ../<repo>/fpga/openxc7-synth/gf128_decode_fp64.v \
                            ../<repo>/fpga/openxc7-synth/tb_gf128_decode_fp64.v
vvp gf128_tb
```
