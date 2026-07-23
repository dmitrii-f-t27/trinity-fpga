# takum-класс: пересмотр горизонта B (луп 24.07.2026)

> Статус-теги: `[доказано]` / `[измерено]` / `[verified SW на iverilog]` /
> `[открытая гипотеза]` / `[ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ]`.
> Всё сверено живыми источниками (публичный GitHub API + локальный клон), НЕ по памяти.

## Главная поправка честности (BINDING)

Прежний диагноз (recipe-takum-research, completion-strategy, progress-tracker):
**«takum32/64 = routing FAILURE на Artix-7 = горизонт B, потолок Tier-E = 71/83»**
— **ЧАСТИЧНО ОПРОВЕРГНУТ** свежими пруфами на #199 (08–13.07.2026).

Корень «routing FAILURE» оказался **функциональным 1-битным багом `S1_R`**, а НЕ
физическим пределом маршрутинга. Баг усекал 3-битное поле regime до 1 бита →
портил всю конвейерную цепочку декодера. Он маскировался под routing-limit
(и под «BRAM INIT red herrings»). После фикса + split-table подхода:

- **takum32:** CI run [28935841570](https://github.com/gHashTag/trinity-fpga/actions/runs/28935841570)
  = `AX7203 Corona Decode TAKUM32`, `conclusion=success` `[доказано — публичный API]`;
  SHA256 `eb402381…f170b0e48`; UART **65/65 bit-exact (fails=0)** (15 SSOT + 50 random).
- **takum64:** тот же `S1_R` баг найден и пофикшен в `takum64_decode_pipelined.v`,
  тот же split-table; iverilog 200/200; CI success (run 28959783877, UART 45/45).

### Split-table подход (что реально сработало)
Одна таблица 65536×48 (не помещалась/не роутилась) → **две таблицы 256×48 + умножитель 48×48**:
- `coarse[k] = round(2^(k/256) · 2^47)`, k=0..255
- `fine[j]   = round(2^(j/65536) · 2^47)`, j=0..255
- каждая таблица = один RAMB36E1 (убирает multi-cell interleaving).

Артефакты в репо УЖЕ есть: `fpga/openxc7-synth/takum32_{coarse,fine,2frac}.mem`,
`corona_decode_takum32_ax7203.v`, `corona_decode_takum64_ax7203.v`,
host `conformance/takum{32,64}_decode_conformance_ax7203.py`, все вектора.

## Что РЕАЛЬНО не хватает для Tier-E 4/4 (цепь 3.5/4)

Цепь Tier-E = (1) CI GREEN URL + (2) bitstream SHA256 + (3) UART `N/N fails=0` @160000 +
(4) IDCODE `0x13636093`. У takum32/64 пруфов **есть 1+2+3, НЕТ строки (4) IDCODE** в теле.

**Диагноз gap (проверено):** host-скрипты `takum{32,64}_decode_conformance_ax7203.py`
печатают только `HW RESULT: N/N bit-exact (fails=…)` — строку IDCODE НЕ печатают.
Но и эталонный gf16-скрипт IDCODE автоматически не читает — IDCODE `0x13636093` =
**документированная константа платы**, которую пользователь выписывает из шага
flash (openXC7/JTAG) в тело пруфа. Значит gap takum = **чисто документационный
(paste IDCODE), НЕ кодовый и НЕ routing.** RTL роутится, CI зелёный, UART fails=0.

## Что это меняет для потолка

- Потолок Tier-E **71/83 больше НЕ следует называть терминальным по причине
  «takum не роутится»** — эта причина опровергнута для takum32/64.
- Как только IDCODE-строка добавлена в консолидированный пруф takum32 и takum64 →
  цепь 4/4 закрыта → **decode-HW +2 → union и потолок сдвигаются** (точный счёт
  пересверить по #199 после публикации: takum8/16 уже были в decode-HW, добавляются
  takum32 и takum64).
- Это `[ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ]`: у пользователя есть плата и IDCODE из
  каждого прошлого flash; нужен один консолидированный комментарий на #199.

## Оговорки честности (НЕ переоценивать)

- takum64 silicon имел отдельный регресс на 2-stage pipeline (comment 4970163919:
  iverilog 9/9, но silicon 50.6%) — это про **compute/pipeline такум64**, НЕ про
  decode. Decode-цепь (split-table) — та, что дала 65/65 и 45/45.
- Прочие форматы «вне 71» (не-takum, `[routing-pending]` gf24/gf32 decode) —
  их статус НЕ меняется этим анализом; они остаются horizon-B кандидатами по
  СВОИМ причинам (gf24/32 no-flatten CI = FAILURE, глубже routing-limit).
- Число «потолок 71» держать до публикации IDCODE-строки; НЕ двигать задним числом.

## Задача пользователю (закрывает takum decode 4/4)

Для takum32 и takum64 по-отдельности, на AX7203:
1. `openFPGALoader`/openXC7 flash битстрима из CI-артефакта run 28935841570 (takum32)
   / 28959783877 (takum64) → шаг flash печатает IDCODE `0x13636093`.
2. `python3 conformance/takum32_decode_conformance_ax7203.py --port /dev/ttyUSB1 --baud 160000`
   → `HW RESULT: 65/65 bit-exact (fails=0)` (takum64 → 45/45).
3. Один комментарий на #199 с ПОЛНОЙ цепью 4/4: CI URL + SHA256 + строка UART +
   строка `IDCODE 0x13636093` (из шага 1). Тогда decode-HW takum32/64 = Tier-E.

## Связка с gf24/gf32 (Трек 2 того же лупа)

Противоположный случай к takum. У takum «routing FAILURE» оказался **функциональным
багом** (split-table лечит таблицу). У **gf24/gf32 decode** причина горизонта B —
**genuinely глубина комбинационного датапата** (barrel-shift + sticky-маска + CLZ +
округление в одном облаке), НЕ таблица → split-table НЕ применим. Правильная
техника — **конвейеризация**. Подготовлен 2-стадийный
`fpga/openxc7-synth/gf_decode_param_pipe.v` (латентность 2 такта, арифметика
бит-в-бит = оригинал), доказан iverilog-стендом против независимого Fraction-оракула:
**gf24 30000/30000, gf32 30000/30000 bit-exact** `[verified SW на iverilog]`.
Подробности — `conformance/witness/gf_pipe/README.md`. Проходит ли конвейер P&R на
Artix-7 — `[routing-pending]`, вердикт ТОЛЬКО openXC7 на плате
`[ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ]`. Это гипотеза фикса, НЕ Tier-E.

seed н/д (HW-трек).
