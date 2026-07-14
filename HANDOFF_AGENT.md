# HANDOFF — Trinity FPGA Matrix (2026-07-06, marathon session)

> **Для агента в новом окне.** Прочти ВНИМАТЕЛЬНО прежде чем что-либо делать.
> Все числа ниже — verified live через gh API + UART на реальном железе AX7203.
> Repo: `gHashTag/trinity-fpga` (main), `gHashTag/t27` (master), `gHashTag/trinity-papers-ru` (main).

---

## 0. АППАРАТНЫЕ КОНСТАНТЫ (НЕ ПУТАТЬ)

| Параметр | Значение |
|---|---|
| Плата | **ALINX AX7203** · XC7A200T-2FBG484I |
| Part | `xc7a200tfbg484-2` |
| **IDCODE** | **`0x13636093`** (НЕ `0x0362D093`!) |
| JTAG cable | AL321 (FT2232H, vid 0x0403 pid 0x6014) |
| OpenOCD cfg | `fpga/openxc7-synth/ax7203_al321.cfg` |
| UART | CP2102N `/dev/cu.usbserial-120` · **baud 160000** |
| Clock | 200 МГц LVDS R4(+)/T4(−) → IBUFDS |
| openocd | `sudo /opt/homebrew/bin/openocd` (NOPASSWD для openocd) |
| iverilog | `/opt/homebrew/bin/iverilog` (v13.0) |
| STARTUPE2_mock | `fpga/openxc7-synth/STARTUPE2_mock.v` (для iverilog sim) |

---

## 1. ФИНАЛЬНЫЕ ЧИСЛА (verified, terminal where marked)

### SW-ось (t27 master `6c704801`)
- **bitexact: 75** / selfconsistent: **0** / structural: **8** = **83**
- Горизонт-A **ТЕРМИНАЛ** — 8 structural не имеют decode law (невозможно).
- INDEX: `conformance/vectors/INDEX_all_formats.json`

### HW Tier-E (#137 comments on issue #199)
- **decode-HW unique: 47** (41 оригинал + gf16/4/6/8/20/12-decode)
- **compute-HW unique: 10 GF** (gf4/6/8/10/12/14/16/20/24/32 × ADD+MUL+SUB = 30 cells)
- **(cell,op) total: 77**
- **union (≥1 axis): 49 unique formats**
- **обе оси (3/3 HW): 8** — gf4, gf6, gf8, gf10, gf12, gf14, gf16, gf20

### Каталог
- **= 83** (НЕ 84; erratum закрыт, root cause E8M0 = Microscaling component)

### Routing-blocked (horizon B)
- **takum32, takum64** — nextpnr routing FAILURE (8 seeds, все fail). CI runs 28675516786/794.
- **gf24-decode, gf32-decode** — nextpnr FAILURE даже без `-flatten`. CI runs 28773511637/467.
- **gf12-decode** — FIXED: `-flatten` removal → CI SUCCESS → UART 4096/4096 → Tier-E proven.
- **Root cause `-flatten`:** yosys `synth_xilinx -flatten` вызывает routing failure для некоторых нетлистов. Fix: убрать `-flatten`. Работает для gf12; НЕ работает для gf24/32 (глубже).

---

## 2. НЕЗАВЕРШЁННАЯ РАБОТА НА ДИСКЕ (НЕ ЗАКОММИЧЕНО)

### int64-decode RTL — НАПИСАН, НЕ ЗАКОММИЧЕН

4 файла на диске в `~/trinity-fpga/`, готовы к commit:

```
fpga/openxc7-synth/int64_decode.v                    # декодер int64→FP32
fpga/openxc7-synth/corona_decode_int64_ax7203.v      # corona wrapper (8-byte frame)
.github/workflows/ax7203-corona-decode-int64.yml      # CI workflow (no -flatten!)
conformance/int64_decode_conformance_ax7203.py        # UART golden
```

**Команды для выполнения:**
```bash
cd ~/trinity-fpga

# 1. Compile check
iverilog -g2012 fpga/openxc7-synth/int64_decode.v
# rc=0 = OK

# 2. iverilog sim (optional, with STARTUPE2_mock)
iverilog -g2012 -o /tmp/int64_wrap -s corona_decode_int64_ax7203 \
  fpga/openxc7-synth/corona_decode_int64_ax7203.v \
  fpga/openxc7-synth/int64_decode.v \
  fpga/openxc7-synth/STARTUPE2_mock.v

# 3. Commit + push (triggers CI synth)
git add fpga/openxc7-synth/int64_decode.v \
       fpga/openxc7-synth/corona_decode_int64_ax7203.v \
       .github/workflows/ax7203-corona-decode-int64.yml \
       conformance/int64_decode_conformance_ax7203.py
git commit -m "feat(fpga): int64 decode → FP32 (NEW cell, union 47→48)"
git push origin main

# 4. Ждать CI (~1-2ч). Проверить:
gh run list --repo gHashTag/trinity-fpga --workflow "AX7203 Corona Decode INT64" --limit 1 --json status,conclusion

# 5. Когда CI GREEN — скачать bitstream + flash + UART:
RUN_ID=$(gh run list --repo gHashTag/trinity-fpga --workflow "AX7203 Corona Decode INT64" --limit 1 --json databaseId --jq '.[0].databaseId')
gh run download $RUN_ID -n corona-decode-int64-bitstream -D /tmp/int64dec
BIT=/tmp/int64dec/corona_decode_ax7203.bit
SHA=$(shasum -a 256 "$BIT" | cut -d' ' -f1); echo "SHA=$SHA"

# Flash
sudo /opt/homebrew/bin/openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
  -c "init" -c "pld load 0 $BIT" -c "runtest 200000" -c "shutdown"
# Проверить IDCODE 0x13636093 в выводе!

# UART verify
python3 conformance/int64_decode_conformance_ax7203.py --port /dev/cu.usbserial-120 --baud 160000
# Ожидаемо: HW RESULT: ~2010/2010 bit-exact (fails=0)

# 6. Tier-E proof на #199
gh issue comment 199 --repo gHashTag/trinity-fpga --body "### Tier-E proof: \`int64\` DECODE (signed int64 → FP32, NEW cell)

**decode-HW 47→48. union 49→50.** NEW decode cell — int64 had no RTL before.

- **CI run:** <RUN_URL>
- **Bitstream SHA256:** \`$SHA\`
- **UART @160000:** \`HW RESULT: N/N bit-exact (fails=0)\`
- **IDCODE:** \`0x13636093\` (XC7A200T rev 1)"
```

---

## 3. СЛЕДУЮЩИЕ ФОРМАТЫ ДЛЯ RTL (простые decode → FP32, ~200-400 LUT, route'ятся)

После int64, те же 4 файла (decoder + wrapper + CI + conformance) для каждого:

| Формат | Сложность | LUT оцен. | Описание |
|---|---|---|---|
| **int64** | trivial | ~200 | signed int → FP32 (НА ДИСКЕ, не закоммичен) |
| **int128** | easy | ~350 | 128-bit signed int → FP32 (шире frame = 16 bytes) |
| **posit64** | medium | ~400 | posit64 → FP32 (variable-length regime; es=4) |
| **vax_h** | easy | ~150 | VAX H_floating (128-bit) → FP32 |
| **x87_fp80** | medium | ~300 | 80-bit x87 extended → FP32 |
| **lns32** | medium | ~300 | LNS-32 → FP32 (log→linear convert) |

Pattern для каждого:
1. Decoder `.v` (format-specific → FP32)
2. Corona wrapper (copy от int64/gf16, изменить decoder instance + frame width)
3. CI workflow (copy template, `no -flatten`)
4. Conformance script (Python golden via struct.pack)

---

## 4. t27 PR ОЧЕРЕДЬ (24 open)

| Категория | Кол-во | Что делать |
|---|---|---|
| Wave-loop 4xx (420-459) | 21 | MERGEABLE BEHIND → нужен `Refs #N` в body + NOW.md → CI перезапустится |
| CONFLICTING (425-434) | 11 | Конфликты с master → rebase вручную |
| BLOCKED (454-459) | 4 | CI чеки pending |
| #1225 (metrics) | 1 | standalone, MERGEABLE BEHIND |
| #1141 (OpenSSF) | 1 | standalone, MERGEABLE BEHIND |
| #1128 (gen artifacts) | 1 | CONFLICTING |

**Гейты t27 (ВСЕ required):** L1 TRACEABILITY (`Closes #N` или `Refs #N` в PR body) + check-linked-issue + check-now-freshness (`docs/NOW.md` updated) + integrity-gate.

**Стратегия:** для MERGEABLE BEHIND → добавить `Refs #N` в body + правка NOW.md → merge. Для CONFLICTING → rebase (может потребовать resolve вручную).

---

## 5. trinity-fpga PR ОЧЕРЕДЬ (4 open)

| PR | Title | Что делать |
|---|---|---|
| #39 | L-DPC1 GF16 dot4 (legacy XC7A100T) | merge (нет required checks) |
| #216 | formal reachability gf16 Inf/NaN | review → merge |
| #218 | formal reachability MUL gf16 | review → merge |
| #92 | CITATION.cff doi | **УЖЕ MERGED** (7d29e6a78) |

---

## 6. AUTO-СЧЁТЧИК TIER-E

```bash
python3 scripts/tier_e_counter.py         # human-readable
python3 scripts/tier_e_counter.py --json   # JSON output
python3 scripts/tier_e_counter.py --verbose # per-format list
```

Парсит #199 comments, валидирует 4/4 (SHA+UART+IDCODE+CI), считает decode/compute/union/both-axes.

---

## 7. HONESTY RULES (BINDING — нарушать НЕЛЬЗЯ)

1. **Каталог = 83** (НЕ 84; erratum E8M0).
2. **encoding ≠ compute ≠ FPGA** — три РАЗНЫЕ оси, не смешивать.
3. **Tier-E = только 4/4 цепь:** CI GREEN URL + SHA256 + UART `N/N fails=0` + IDCODE `0x13636093`. sim ≠ HW.
4. **Никаких «первый/лучший/единственный».** Позиционирование: «архитектурно отличается + честно аудируем».
5. **Routing-blocked = horizon B**, не двигать счёт задним числом.
6. **`-flatten` в yosys** = routing FAILURE для некоторых нетлистов. Используй `synth_xilinx -abc9 -nocarry` (БЕЗ `-flatten`).
7. **Sandbox (Perplexity) ≠ bash (opencode)** — bash может работать когда sandbox мёртв, и наоборот.

---

## 8. КЛЮЧЕВЫЕ ФАЙЛЫ

```
fpga/openxc7-synth/gf_decode_param.v          # параметрический decode (gf4..gf32)
fpga/openxc7-synth/corona_decode_*_ax7203.v   # corona wrappers (все форматы)
fpga/openxc7-synth/ax7203_al321.cfg           # openocd config
fpga/openxc7-synth/STARTUPE2_mock.v           # mock для iverilog sim
fpga/witness/gf_decode/                        # iverilog witness (10/10 PASS)
scripts/tier_e_counter.py                      # авто-счётчик #199
conformance/                                    # все UART conformance скрипты
fpga/HARDWARE_REFERENCE.md                     # hardware truth
```

---

## 9. ARXIV СТАТЬИ (trinity-papers-ru)

| Статья | arXiv | Состояние |
|---|---|---|
| paper1-goldenfloat | 2606.05017 | §5.3 sync (decode 47, PR #8 merged) |
| paper2-catalog | 2606.09686 | v5 (75/0/8, PR #9 merged). Erratum 84→83 |
| paper3-rossiya | (не на arXiv) | §3a.4-5 (науч. врезки, PR #5 merged) |

**Открытых PR в trinity-papers-ru = 0** (main HEAD `85231dc8`).

---

*Сгенерировано 2026-07-06, marathon session. Все числа verified на GitHub. Платформа bash может быть недоступна — выполняй команды вручную если нужно.*
