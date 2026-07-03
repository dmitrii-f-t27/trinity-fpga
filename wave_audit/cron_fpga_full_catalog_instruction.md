# Cron-loop: автономная FPGA-проверка всех форматов на локальной AX7203

> **Source:** drafted by owner 2026-07-03, saved to repo (version-controlled) because
> the skill-write sandbox was down (500: Failed to place sandbox). Promote to the
> `trinity-wave-loop` skill as `references/cron-fpga-flash-loop.md` via `save_custom_skill`
> when sandbox returns. Verified against live HEAD of gHashTag/trinity-fpga (issue #199,
> status 03–04.07.2026): decode-HW 41, compute-HW 30, Tier-E ~71/73, ceiling 73/83,
> board AX7203 IDCODE 0x13636093.

## 0. Инварианты (нарушать нельзя)

- **Плата:** AX7203 = XC7A200T-2FBG484I, part `xc7a200tfbg484-2`, IDCODE `0x13636093` (НЕ `0x0362D093`). Клок 200 МГц LVDS R4(+)/T4(−) → IBUFDS.
- **Tier E засчитывается ТОЛЬКО при полной цепи на #199:** (a) CI run URL (bitstream GREEN) + (b) bitstream SHA256 + (c) UART-лог `HW RESULT: N/N bit-exact (fails=0)` @160000 baud + (d) подтверждённый IDCODE `0x13636093`. Нет одного из четырёх → это НЕ Tier E.
- **encoding ≠ compute ≠ FPGA.** 2-oracle SW (Python golden == Corona RTL в симуляции) — это `[verified SW]`, НЕ decode-HW. Симуляция `sim N/N bit-exact` ≠ HW.
- **Потолок = 73/83** (10 structural-форматов непрошиваемы — нет single-value decode law). Никогда не гнаться за 83/83.
- **Каталог = 83 формата** (НЕ 84). SSOT = `specs/numeric/formats_catalog.t27` в репо t27.
- **Никаких категорических утверждений.** Статус-теги: `[доказано]`/`[verified SW]`/`[измерено на кремнии]`/`[routing-pending]`/`[ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ]`.
- `confirm_action` перед любым push/merge в публичный репо. Синтез/прошивка идёт на локальной машине пользователя (вне песочницы) → всегда `[ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ]`, крон не может сам прошить.

## 1. Что крон МОЖЕТ и что НЕ МОЖЕТ

**Может (без железа, в песочнице/через API):**
- Читать состояние #199 через `api.github.com` → считать текущие decode-HW / compute-HW / Tier-E.
- Проверять статус CI-прогонов (bitstream GREEN / routing-pending / fail) через `actions/runs`.
- Верифицировать SHA256 и наличие UART-proof в комментариях (анти-fake-pass).
- Готовить следующую ячейку: RTL-скелет по шаблону (track-a decode-порт / track-b new-RTL / compute-GF), golden-oracle (mpmath/Fraction @120-bit, RNE+sticky), sim-testbench.
- Формировать очередь задач и шаблон комментария Tier-E для локального агента.

**НЕ может (только локальный агент на машине пользователя):**
- `pld load` битстрима, `runtest`, физический UART-conformance → это burst-flash, вне песочницы.
- Промоутить ячейку в Tier E без реального UART-лога.

## 2. Один атомарный цикл крона (каждые N минут)

```
ВХОД:
  1. fetch api.github.com/repos/gHashTag/trinity-fpga/issues/199 (тело + счётчики)
     + comments?per_page=100&page=1..2 → распарсить последние Tier-E proof-комментарии.
  2. Свести живой счёт: decode-HW, compute-HW, Tier-E total, потолок 73.

ДЕЙСТВИЕ (depth-first, приоритет по порядку):
  A. Проверить routing-pending ячейки (takum32/64, lns16 re-flash):
     - если CI run стал GREEN + есть SHA256 → готово к flash → в очередь локальному агенту.
     - если CI ещё идёт → [routing-pending], пропустить.
  B. Если есть Tier-C ячейка (sim-verified, битстрим есть, UART нет) →
     сформировать flash-задачу + шаблон Tier-E комментария.
  C. Иначе взять следующий НЕпрошитый формат из каталога 83 по depth-first
     (compute-GF семейство раньше breadth-decode) → подготовить RTL-скелет
     + golden-oracle + sim-testbench, запустить CI-synth (docker-retry, per-seed
     --signal=KILL timeout).

ГЕЙТ (анти-fake-pass, правило falsifier):
  - Ячейку промоутить в Tier E ТОЛЬКО при 4/4 (CI GREEN + SHA256 + UART N/N fails=0 + IDCODE).
  - sim-bitexact ≠ HW. Никогда не засчитывать симуляцию как HW.
  - Если UART-лог отсутствует → ячейка остаётся Tier C, крон НЕ трогает счёт.

ВЫХОД:
  - Если появилась НОВАЯ Tier-E ячейка с полным пруфом → send_notification (формат, счёт N/83, CI URL).
  - Если ничего нового → завершить run молча (без notification).
  - Если 2+ подряд [BACKGROUND CRON FAILED] по одной причине → НЕ долбить, оставить
    инструкцию как есть (пользователь: крон НЕ останавливать, только улучшать инструкцию).
```

## 3. Шаблон burst-flash для локального агента (AX7203, вне песочницы)

Крон кладёт это в задачу локальному агенту; сам flash делает агент на машине:

```
# 0. Разблокировать JTAG при LIBUSB_ERROR_ACCESS:
pkill -f openocd; sudo kextunload -b com.apple.driver.AppleUSBFTDI 2>/dev/null; # + power-cycle платы при упорстве
# 1. Атомарный шаг на формат:
openocd -f <cfg> -c "init; pld load 0 <format>.bit; runtest 10000; exit"   # flash битстрима
<uart_conformance_runner> --port /dev/cu.usbserial-120 --baud 160000 | tee logs/<format>_hw.log
# 2. Стоп-правило утечки дескриптора: pkill -f openocd каждые ~5 циклов.
# 3. fmt-коды decode 0–12 (tf32 = 7-байт кадр). Публикация Tier E:
gh issue comment 199 --repo gHashTag/trinity-fpga --body "<шаблон ниже>"
```

**Шаблон Tier-E комментария:**

```
### Tier-E proof: `<format>` (decode|compute)
decode-HW N->N+1. Tier-E M.
- CI run: https://github.com/gHashTag/trinity-fpga/actions/runs/<id>
- Bitstream SHA256: `<sha256>`
- IDCODE: `0x13636093` ✅ | Flash: <s>s, rc=0
- UART conformance: `HW RESULT: N/N bit-exact (fails=0)` @160000 baud, /dev/cu.usbserial-120
```

## 4. Стоп-правило и честность

- Крон останавливает промоушен на **73/83** (потолок). Дальше только SW-track (69→73 в t27) и correctness-fix уже-proven ячеек.
- Расхождение публичных цифр (напр. каталог 83 vs препринт 84) → готовить erratum, не тихо править.
- Каждый заявленный скачок счёта крон обязан сверить через API (`gh`/`api.github.com`) прежде чем принять — урок «проверка не того репо → ложное коммит-не-найден».

## 5. Pending owner actions (when sandbox returns)

- [ ] Save this file as `references/cron-fpga-flash-loop.md` in the `trinity-wave-loop` skill via `save_custom_skill`.
- [ ] Create issue about dead nf4-kernel in `gHashTag/trios-trainer-igla` (draft approved, English body).
- [ ] Save `igla-race-format-benchmark.md` reference (repo map of trios-*, two BPB cuts — frozen champion + live matrix-ledger, falsifier_2-warning, top format tables, API-fallback patterns).
- [ ] Bind to cron: see recommendation below.
