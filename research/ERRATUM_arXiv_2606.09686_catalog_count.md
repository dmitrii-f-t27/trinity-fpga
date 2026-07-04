# Erratum v2 — arXiv:2606.09686 (каталог числовых форматов)

**Статья:** *An 84-Format Numeric Catalog with Bit-Exact Conformance Vectors: A Vendor-Neutral Reference for FP8, BF16, MXFP4, and Microscaling Formats*, D. Vasilev, [arXiv:2606.09686](https://arxiv.org/abs/2606.09686), submitted 2026-06-08.
**Тип правки:** correctness (счёт форматов) — блокирует HW-replay-усиление до выхода.
**SSOT:** `specs/numeric/formats_catalog.t27` (репо gHashTag/t27, ветка master).
**Проверено:** 2026-07-04 — прямой подсчёт `grep -c "// CATALOG: id="` = **83**, дубликатов id нет; кластеров (families) ровно **13**.

---

## 1. Суть расхождения

| Что | Опубликовано (v1) | SSOT (факт) |
|---|---|---|
| Число форматов | **84** | **83** |
| Число families | 13 | 13 ✓ (совпадает) |

Заголовок и аннотация v1 заявляют «catalog of **84** numeric formats spanning 13 families». Актуальный SSOT `formats_catalog.t27` содержит **83** записи `// CATALOG:` без дублей. Families (кластеры) совпадают — расхождение только в числе форматов, дельта = 1.

## 2. Корень дельты 84 → 83 [установлено]

Из 6 conformance-pack'ов, перечисленных в аннотации (GF16, MXFP4 element, BF16, FP8 E4M3, FP8 E5M2, **E8M0 block scale**), пять имеют самостоятельные строки в SSOT-каталоге:

- `gf16`, `mxfp4`, `bfloat16`, `fp8_e4m3`, `fp8_e5m2` — присутствуют как отдельные записи каталога;
- **`e8m0` (block scale) — НЕ является отдельной строкой каталога.** E8M0 — это масштаб-компонент (shared exponent) микроскейл-блока, входящий в `mxfp4/mxfp6/mxfp8` (кластер Microscaling), а не самостоятельный числовой формат.

Наиболее вероятная причина числа 84 в v1 — учёт E8M0 block scale как отдельного формата наравне с элементными форматами. Канонический SSOT трактует E8M0 как компонент микроскейлинга, поэтому каноническое число = **83**.

> Примечание: наличие conformance-pack'а для E8M0 корректно и остаётся в силе — pack покрывает block-scale-компонент. Это не отменяет pack, а только уточняет, что E8M0 не считается отдельной строкой каталога.

## 3. Исправления (v1 → v2)

1. **Заголовок:** «An **84**-Format Numeric Catalog …» → «An **83**-Format Numeric Catalog …».
2. **Аннотация:** «a catalog of **84** numeric formats spanning 13 families» → «a catalog of **83** numeric formats spanning 13 families».
3. **Все вхождения "84" в теле статьи**, ссылающиеся на размер каталога → **83**. Число families (13) не меняется.
4. Добавить сноску: «E8M0 block scale is covered by a dedicated conformance pack but is enumerated as the shared-exponent component of the Microscaling family, not as a standalone catalog row; the canonical catalog size defined by `formats_catalog.t27` is 83.»

## 4. Что НЕ меняется

- 13 families — верно.
- Шесть conformance-pack'ов (включая E8M0) — верны, остаются.
- Идентичность φ² + φ⁻² = 3 как anchor-vector — верна.
- P3109 v3.2.0 cross-walk — не затрагивается.
- Заявка «registry filling, no new formats, no superiority claims» — сохраняется.

---

## EN version (for arXiv erratum / v2 comment)

**Erratum (v2).** The v1 title and abstract state a catalog of *84 numeric formats spanning 13 families*. The single source of truth `specs/numeric/formats_catalog.t27` (repo gHashTag/t27, master) contains **83** catalog records with no duplicate ids; the family count (13) is unchanged. The discrepancy of one arises from counting the **E8M0 block scale** as a standalone format: E8M0 is the shared-exponent component of the Microscaling family (mxfp4/6/8), covered by its own conformance pack, but not enumerated as a standalone catalog row. The canonical catalog size is therefore **83**. All occurrences of "84" referring to the catalog size are corrected to **83**; the six conformance packs (including the E8M0 pack) and the φ²+φ⁻²=3 anchor identity are unchanged.

---

## Действия

- [ ] Обновить `docs/arxiv-submission/*` и исходник статьи каталога: 84 → 83 (по п.3).
- [ ] Выпустить v2 на arXiv с этим erratum-комментарием.
- [ ] Только ПОСЛЕ v2 — прикладывать random-10 HW-replay к второй статье (иначе рецензент поймает 84 vs replay-из-83).

*Все утверждения проверены против живого SSOT 2026-07-04. Дельта установлена (E8M0), число families подтверждено (13).*
