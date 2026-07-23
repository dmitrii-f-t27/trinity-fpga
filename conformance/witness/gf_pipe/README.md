# gf24/gf32 decode — pipelined variant + iverilog witness (horizon-B routing prep)

**Дата:** 2026-07-24. **Автор:** Vasilev (gHashTag), ORCID 0009-0008-4294-6159.
**Статус:** `[verified SW на iverilog]` (функция). Synth/PnR/flash на AX7203 = `[ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ]`.

## Зачем

gf24 (E9/M14/BIAS255) и gf32 (E12/M19/BIAS2047) decode **не проходят routing**
на AX7203 (XC7A200T) при синтезе из чисто-комбинационного `gf_decode_param.v`
(no-flatten CI = FAILURE, runs 28773511637 / 28773514467). Причина —
**НЕ гигантская LUT-таблица** (в отличие от takum, который чинил split-BRAM),
а **глубина одного комбинационного облака**: переменный barrel-shift (до ~40 бит)
+ динамическая sticky-маска + CLZ + округление в одном `always@(*)`. Правильная
horizon-B техника здесь — **конвейеризация датапата**, а не split таблицы.

## Что сделано

- `fpga/openxc7-synth/gf_decode_param_pipe.v` — 2-стадийный конвейер того же
  decode-закона (латентность 2 такта). Регистр вставлен ПОСЛЕ классификации +
  true_exp + вычисления shift, ПЕРЕД barrel-shift + округлением + FP32-pack.
  **Арифметика бит-в-бит идентична** `gf_decode_param.v` (те же iverilog-фиксы:
  widen-before-shift #1, `[23:0] sub_shifted` OOB-read #2). Изменена ТОЛЬКО
  временна́я структура, не функция.

## Пруф (независимый 2-й witness)

- `gf_decode_pipe_oracle.py` — golden Fraction-оракул gf{N}→FP32 (точный
  рациональный decode + RNE к binary32). **Структурно независим** от Verilog.
  Само-проверен: `oracle_selfcheck.py` = 200k fp32 round-trips бит-в-бит vs numpy.
- `tb_gf_decode_param_pipe.v` — self-checking iverilog-стенд (по одному вектору
  с полным сбросом конвейера, без streaming-неоднозначности).

### Результаты (iverilog 12.0)

| Формат | Поля | Векторов | Результат |
|---|---|---|---|
| gf24 | E9/M14/BIAS255 | 30000 (repr.+5-class corners) | **30000/30000 bit-exact** |
| gf32 | E12/M19/BIAS2047 | 30000 (repr.+5-class corners) | **30000/30000 bit-exact** |

Контроль: чисто-комбинационный `gf_decode_param.v` на тех же векторах = 30000/30000
(оракул согласован и с оригиналом, и с numpy — тройная сверка).

yosys generic synth (`synth -flatten`, gf32): 1927 ячеек, 73 FF (2 стадии
подтверждены). **Это `[смоделировано]`, НЕ P&R** — вердикт по routing даёт
только openXC7 на плате.

## Воспроизвести

```bash
cd conformance/witness/gf_pipe
python3 oracle_selfcheck.py                                   # оракул vs numpy
python3 gf_decode_pipe_oracle.py --N 24 --E 9  --M 14 --BIAS 255  --count 30000 --out vec_gf24.txt
python3 gf_decode_pipe_oracle.py --N 32 --E 12 --M 19 --BIAS 2047 --count 30000 --out vec_gf32.txt
iverilog -g2012 -DN=24 -DE=9  -DM=14 -DBIAS=255  -DVEC='"vec_gf24.txt"' -DNVEC=30000 \
  -o s24.vvp ../../../fpga/openxc7-synth/gf_decode_param_pipe.v tb_gf_decode_param_pipe.v && vvp s24.vvp
iverilog -g2012 -DN=32 -DE=12 -DM=19 -DBIAS=2047 -DVEC='"vec_gf32.txt"' -DNVEC=30000 \
  -o s32.vvp ../../../fpga/openxc7-synth/gf_decode_param_pipe.v tb_gf_decode_param_pipe.v && vvp s32.vvp
```

## Честные границы

- Это **гипотеза** фикса routing: конвейер сокращает критический путь, но
  проходит ли gf24/gf32 P&R на Artix-7 — **проверяется ТОЛЬКО на плате**
  (openXC7 nextpnr-xilinx недоступен в песочнице). `[routing-pending]`.
- iverilog доказывает **функцию** (encoding decode), НЕ Tier-E. Tier-E = полная
  цепь 4/4 (CI GREEN + SHA256 + UART N/N fails=0 @160000 + IDCODE 0x13636093).
- Латентность выросла с 0 (комб.) / 1 (OUT_REG) до 2 тактов — host-скрипт
  UART-conformance должен учесть 2-тактовую задержку при чтении результата.
- Представительная выборка (30k + 5-class corners), НЕ exhaustive (gf32 = 2³²
  недостижимо в песочнице; полный gf24 = 2²⁴ = 16.7M возможен на плате).
