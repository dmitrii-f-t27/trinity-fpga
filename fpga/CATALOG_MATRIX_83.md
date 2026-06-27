# Матрица каталога: 83 формата × {SW-conformance / FPGA-перенос}

> Стартовая карта для focused-сессии «прошить полный каталог» на AX7203 (XC7A200T).
> Все статусы — из HEAD `gHashTag/t27` SSOT. [verified HEAD]

## Сводка
- **83** формата (total_formats, INDEX_all_formats.json)
- **55** bit-exact паков (вкл. 6 self-consistent)
- **22** structural паков
- **14** P0 (Corona RTL готов + bit-exact) — быстрый перенос
- **47** P1 (bit-exact, RTL писать) — средняя стоимость
- **22** P2 (structural, нужен bit-exact генератор) — бэклог

## P0 — Corona RTL готов + bit-exact (14) — БЫСТРЫЙ ПЕРЕНОС
| Формат | SW | n_vec | Corona RTL | FV | FPGA |
|--------|-----|-------|------------|-----|------|
| bfloat16 | bit-exact | 0 | ✅ bf16_decode.v | ✅ | ☐ |
| fp4_e2m1 | bit-exact | 16 | ✅ fp4_decode.v | ✅ | ☐ |
| fp6_e2m3 | bit-exact | 64 | ✅ fp6_e2m3_decode.v | ✅ | ☐ |
| fp6_e3m2 | bit-exact | 64 | ✅ fp6_e3m2_decode.v | ✅ | ☐ |
| fp8_e4m3 | bit-exact | 0 | ✅ fp8_e4m3_fnuz_decode.v | ✅ | ☐ |
| fp8_e5m2 | bit-exact | 0 | ✅ fp8_e5m2_decode.v | ✅ | ☐ |
| int4 | bit-exact | 16 | ✅ int4_decode.v | ✅ | ☐ |
| int8 | bit-exact | 256 | ✅ int8_decode.v | ✅ | ☐ |
| lns8 | bit-exact | 256 | ✅ lns8_decode.v | ✅ | ☐ |
| mxfp4 | bit-exact | 0 | ✅ fp4_decode.v | ✅ | ☐ |
| mxfp8 | bit-exact | 256 | ✅ mxfp8_e4m3_decode.v | ✅ | ☐ |
| nf4 | bit-exact | 16 | ✅ nf4_decode.v | ✅ | ☐ |
| posit8 | bit-exact | 256 | ✅ posit8_decode.v | ✅ | ☐ |
| tf32 | bit-exact | 8 | ✅ tf32_decode.v | ✅ | ☐ |

## Достигнуто на AX7203 [verified 2026-06-27]
| Формат | SW | FPGA encoding | FPGA ADD |
|--------|-----|---------------|----------|
| gf4 | bit-exact | ✅ 6/6 | ☐ (ALU pass-through) |
| gf8 | bit-exact | ✅ 7/7 | ☐ |
| gf12 | bit-exact | ✅ 7/7 | ☐ |
| gf16 | bit-exact | ✅ 10/10 | ☐ (ALU pass-through) |

## Инфраструктура (полностью отлажена)
- UART: CP2102N `/dev/cu.usbserial-120`, TX=N15, RX=P20, CFGMCLK ≈70 МГц
- CI: seed-search 1..8 + routing-guard, БЕЗ --force
- Conveyor: parameterized `gf_conformance_ax7203.py` + identity-echo bitstream
- ALU: pass-through (нужен реальный ADD для compute-conformance)
