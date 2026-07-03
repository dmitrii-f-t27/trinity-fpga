# IGLA RACE: бенчмарк форматов (карта trios-*, два среза BPB, честная рамка)

## Когда использовать
Когда Dmitrii/gHashTag просит про IGLA RACE, топ-формат для задачи, BPB-числа,
матрицу Format×Algorithm, или «какой числовой формат учится лучше».

## Карта репозиториев (trios-*)
- **Ядро:** `gHashTag/trios-trainer-igla` (default `main`, **English-only**, правило PR #65).
  SSOT training pipeline: JEPA-T + transformer + NCA, Rust-only, ASHA scheduler.
  Метрика = BPB на tiny_shakespeare. Матрица Format×Algorithm = 351 ячейка
  (39 форматов × 9 оптимизаторов) в `ssot.bpb_samples`, авто-PR matrix_ledger.
  Topics: igla-race, jepa, transformer, training. Anchor φ²+φ⁻²=3.
- **Companion:** trios-railway, trios-mcp, trios-railway-mcp, trios-mcp-rag, trios-dwagent.

## ДВА СРЕЗА BPB — НЕ ПУТАТЬ (расходятся, масштаб решает)

### Срез A — Frozen champion (issue #181, hidden=828, frozen 2026-05-25)
Все значения = [Открытая гипотеза] (sub-Chinchilla, предварительно):
- champion **binary32 = 2.1919**
- fp16 = **2.5501** > gf16 = **2.5725** > bf16 = **2.6135**
- gf8 = **2.9322** = posit8
- Только GF16 реально измерен + имеет FPGA-данные (35/35 tb @ 323 МГц Artix-7).
- Честная рамка: «the method survives, phi does not (yet)».

### Срез B — Live matrix-ledger (PR #216, commit fab7d81, run 28643449889, hidden=96, step=3000)
⚠️ **ВСЕ 88 строк falsifier_2_hit=true** → smoke-масштаб, НЕ champion. Топ обучаемости (delta_bpb):
- fp8_e4m3 adamw delta **0.333** > int4 muon **0.304** > int8/fp8_e5m2 muon **~0.096**
  > floats fp32/fp16/fp80/posit16 **~0.05** (muon only) > gf16 muon **0.026**
- **nf4 МЁРТВ: bpb=7.0 ровно, delta=0** на всех сидах/алго (untrained ceiling = log2 alphabet).
- adamw без muon = delta≈0 почти везде.

**Вывод:** frozen и live срезы РАСХОДЯТСЯ → у IGLA нет устойчивого топ-формата.
Frozen champion — binary32; live top-learnability — fp8_e4m3/int4 под muon.

## Loop/фальсификатор статусы
- **Loop 11 (#183):** INSUFFICIENT_EVIDENCE (phi 5.9871 vs zoo 6.0454, overlapping CI,
  P(phi<zoo)=0.976 ниже порога, n<11).
- **F2 proxy (#182):** ZOO WINS accuracy (mean_diff +0.67, p~1.6e-12); phi 0 lossy
  conversions vs zoo 1024 (breadth-moat, недоказан).
- **falsifier_2** = anti-fake-pass guard (#103/#106) — метит невалидные/plateau прогоны.

## Научный фон 2026 (для ИИ-инженеров)
- FP8 = стандарт train+inference, <0.5-1% MMLU потеря (TensorRT-LLM).
- NVFP4 > MXFP4 (MXFP4 требует +36% токенов, NVIDIA).
- INT8 бьёт FP8 после RHT (HyperQuant, arXiv:2606.23406).
- takum = «live threat» для GoldenFloat (Hunhold 2024, arXiv:2412.20273).

## API-fallback паттерны (когда песочница мертва)
- Тело issue: `api.github.com/repos/<o>/<r>/issues/<n>`
- Комментарии: `.../comments?per_page=100&page=N`
- PR files/patch: `.../pulls/<n>/files`
- Raw файл: `raw.githubusercontent.com/<o>/<r>/<branch>/<path>`
- GitHub Search API без токена = 403/uncrawlable → использовать ЛИСТИНГ issues, не поиск.
- `fetch_url` на эти хосты работает БЕЗ песочницы; memory_* тоже.
