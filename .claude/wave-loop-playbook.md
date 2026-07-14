# Wave-луп v2 — Playbook итерации (каждые 15 мин)

> Канонический SOP для каждого запуска Wave-лупа. Сохраняет итоги сессии
> 2026-06-26 (FPGA-диагностика AX7203). Cron: `*/15 * * * *` (session-only).

Каждый шаг = ВХОД → ДЕЙСТВИЕ → ГЕЙТ. Гейт не пройден → стоп. Язык = русский, романизация Vasilev.

## §0 Цель «прошить полный каталог»
- **SSOT** = `gHashTag/t27/formats_catalog.t27` (PR #1028), НЕ в trinity-fpga.
- **СЧЁТ = 83** [verified HEAD t27: INDEX_all_formats.json total_formats=83, total_packs=83, bitexact_packs=55, structural=22, selfconsistent=6]. 84=arXiv erratum; 80/77=устаревшие снимки Corona ROM.
- Бит-точные паки есть для **6**: GF16, MXFP4elem, BF16, FP8 E4M3, FP8 E5M2, E8M0.
- **Corona** (`gHashTag/tt-trinity-corona`) = read-only oracle GF180/TTGF26b: REUSE `formal/fv_*.sv` (формальная эквивалентность > векторов) + `post_silicon/corona_vectors.py` (генератор, протокол op+a+b→result); 17 Tier-1 RTL-декодеров, остальное ROM; **≠ AX7203-compute** (другие примитивы/тайминг — переиспользуем логику+FV, не битстримы).
- Три цели: SW-conformance (6→все), HW-conformance (FPGA bit-exact via `/dev/cu.usbserial-120`), Multi-width RTL (GF4–GF256).
- Веха: матрица **[формат × {SW✓, FPGA✓}]**.

## §1 ГЕЙТ-0 — контекст/честность
Память + HEAD/PR/watchdog + гейты прошлого лупа.

## §2 Шаг 1 — аудит (gh, ОБА репо)
trinity-fpga (FPGA) + gHashTag/t27 (каталог) + tt-trinity-corona (oracle) → реестр ТЕХ/НАУЧ/ПРАВ/СТРАТ × P0/P1/P2.

## §3 Шаг 2 — научный обзор 2025–2026
Lean/Coq/Flocq, ZKML, GreenAI, троичные FPGA/ASIC, Sail ISA. ≥1 источник/линия или «ничего нового».

## §4 КРИТИКА генерала (обязательно)
- Фактчек констант.
- «Работает» → каким каналом? **Камера = RETIRED** (Nyquist 2.5 Гц, банк вне FOV) — только **электрический дискриминатор**.
- **necessary ≠ sufficient**: «клок осциллирует» ≠ «годен для UART/gf16».
- **workaround ≠ fix**: seed-search, --force, дефолтный порт = обходы.
- Один неизвестный за тест.

## §5 Шаг 3 — план
`implementation_plan`, статусы [СДЕЛАНО]/[В ЛУПЕ]/[ТРЕБУЕТ ПОЛЬЗОВАТЕЛЯ]/[СЛЕД.ЛУП], P0/P1/P2, какие ячейки матрицы закрывает.

## §6 Шаг 4 — реализация
- МОГУ: RTL/XDC/CI (**СТАНДАРТ: seed-search 1..8 + routing-guard grep "Failed to find a route", БЕЗ --force**) + harness + decoder (самотест) + статья/PDF + erratum RU+EN + ветка/PR + flash/UART (сам).
- **Push = confirm_action.**
- Методология: один-неизвестный; CDC multi-bit → Gray; dual-nibble электрический дискриминатор (ref+test ниббл); exact-byte echo (0x55=baud+wire OK; 0x57/0x51=baud-err; тишина=провод мёртв).
- Прошивка: `openocd -f ax7203_al321.cfg -c init -c "pld load 0 …bit" -c "runtest 200000" -c shutdown`; **IDCODE-recheck 0x13636093** после каждой.

## §7 Шаг 5 — отчёт + 3 варианта сотрудничества
`otchet_wave_loop.md` → PDF (`share_file should_validate=false`). Резюме/реестр/обзор/план/матрица/3 варианта (низкий-средний-высокий риск) + рекомендация.

## §8 Финал — обновить скилы
Новые истины → `fpga-hardware-truth.md` + этот playbook; durable → память.

---

## FPGA-ИСТИНЫ [verified 2026-06-26]
- AX7203 = XC7A200T-2FBG484I (`xc7a200tfbg484-2`), IDCODE **0x13636093**.
- LED B13/C13/D14/D15 = **LVCMOS18** (LED1-4, 1-based; **silkscreen-label НЕ verified**).
- rst **T6 LVCMOS15** active-low.
- UART TX=**N15** / RX=**P20** (LVCMOS33) → CP2102N **`/dev/cu.usbserial-120`** (**TX+RX PROVEN alive**); AL321 ch.B (`/dev/cu.usbserial-210512180081`) = **DEAD**.
- 200 МГц R4/T4 DIFF_SSTL15→IBUFDS→BUFG (raw, no PLL): счётчик жив [**23.7/с, доказано**], **НО UART на 200 МГц не отвечает** (gf16+loopback = 0) — **necessary≠sufficient**.
- **CFGMCLK (STARTUPE2) ≈ 69–70 МГц [measured] = PROVEN-клок** (все CFGMCLK-дизайны работают).
- **Камера = RETIRED.** Только электрический дискриминатор.
- **BAUD_DIV = baud хоста**: CFGMCLK-дизайны ~160000, 200 МГц-дизайны ~115200.
- **CI: seed-search 1..8, БЕЗ --force** (--force ships broken `$PACKER_VCC_NET` bitstreams).

## Honesty-чеклист
- Нет «первый/лучший» → [доказано]/[измерено]/[открытая гипотеза]/[требует подтверждения].
- Каталог = 83 (до сверки t27 HEAD).
- 49× энергоэффективность = [гипотеза].
- φ²+φ⁻²=3 = identity-witness.
- FPGA push = confirm_action.
