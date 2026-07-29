# gf256 — строгий SW-bitexact (горизонт A, Trinity Catalog-100)

**Дата:** 2026-07-24. **Автор:** Vasilev (gHashTag), ORCID 0009-0008-4294-6159.

## Что закрыто

gf256 = GF(N=256, E=97, M=158, BIAS=2⁹⁶−1) переведён из `bitexact_selfconsistent`
(FP32-truncating decode conformance) в **строгий SW-bitexact**, 3 witness.
Самый широкий формат приёма gf48/gf96/gf128: **M=158 → округлять 106 бит**
(gf128=26, gf96=7, gf48=0). Канонический BIAS = 2⁹⁶−1 (`scripts/generate_all_formats.py`);
исторический R&D-флаг «bias Experimental» (`GOLDENFLOAT_HW_CONFORMANCE_v0.2:82`) —
не актуален, oracle использует канонический BIAS.

## Три независимых witness (`[доказано]`)

| # | Witness | Реализация |
|---|---------|-----------|
| A | `witness_A` | точный **mpmath** mpf (dps=200 ≫ 158 бит) → `frexp`+scaling+RNE half-cmp |
| B | `witness_B` | pure **integer** field-construct, guard/sticky для 158→52, экспонент ±2⁹⁶ как целое |
| C | `gf256_decode_fp64.v` | fixed-width Verilog, BIAS 96-bit localparam, E2 signed [100:0], 159-bit full_sig, iverilog 13.0 |

```
WITNESS CROSS-CHECK (A mpmath-exact vs B integer-construct): 50230/50230 agree (mismatch=0)
HW RESULT: 50230/50230 bit-exact (fails=0)     # RTL (C) vs oracle
```

Доп. сверка: `m=2^106−1, te=0` → A совпал с `struct.pack` (0x3ff0000000000001).
Покрытие классов: norm 40922, sub 1052, +inf 4005, +0 2120, −0 2127, nan 4.
Границы `te=±1024/−1074` проверены точно. Урок gf96 (signed-sum поля) → сошёлся с 1-го прогона.

## Тир и границы (BINDING)

- **Строгий SW-bitexact** `[доказано]` — НЕ Tier-E (нет AX7203 flash). Синтез/PnR/flash = `[ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ]`.
- Горизонт A: SW-bitexact 72→73, остаток selfconsistent 3→2 (остаются `gf512/1024`).

## Файлы
- `conformance/gf256_bitexact_oracle.py` — witness A + B
- `conformance/gf256_vectors.hex` — 50230 векторов «<256-bit raw> <64-bit expected>»
- `fpga/openxc7-synth/gf256_decode_fp64.v` — RTL witness C
- `fpga/openxc7-synth/tb_gf256_decode_fp64.v` — iverilog testbench

## Воспроизведение
```bash
cd conformance && python3 gf256_bitexact_oracle.py
cp gf256_vectors.hex /tmp/ && cd /tmp
iverilog -g2012 -o gf256_tb ../<repo>/fpga/openxc7-synth/gf256_decode_fp64.v \
                            ../<repo>/fpga/openxc7-synth/tb_gf256_decode_fp64.v
vvp gf256_tb
```
