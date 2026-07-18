#!/usr/bin/env bash
# Абляция fp-карманов тернарной модели Ifrim: FP8 (repro) vs FP8S (scaled e4m3) vs GF8 (e3m4, φ-правило)
# Запуск на поде 8xH100. Базируется на официальном run_cuda_ternary.sh записи
# records/track_10min_16mb/2026-03-24_74M_Ternary_UNet_FP8_10L_8192BPE_YaRN_NeoMuon.
#
# Использование:  ./run_gf8_ablation.sh {fp8|fp8s|gf8} [SEED]
# Ожидаемый вывод: val_bpb в конце тренировки; сравнивать три плеча при ОДИНАКОВЫХ сидах.
# Для значимости — 3 сида на плечо (как требует протокол Parameter Golf: mean по 3 запускам).

set -euo pipefail

ARM="${1:?Укажи плечо: fp8 | fp8s | gf8}"
SEED="${2:-1337}"

case "$ARM" in
  fp8)  export FP_STORAGE=FP8  ;;  # репро официальной записи (прямой cast e4m3)
  fp8s) export FP_STORAGE=FP8S ;;  # контроль: e4m3 + per-row absmax scale
  gf8)  export FP_STORAGE=GF8  ;;  # абляция: GF8 e3m4 + per-row absmax scale
  *) echo "Неизвестное плечо: $ARM"; exit 1 ;;
esac

export SEED="$SEED"
export RUN_ID="ablate_${ARM}_seed${SEED}"

# --- остальные env как в официальном run_cuda_ternary.sh записи Ifrim ---
# (скопируй сюда блок export'ов из оригинального run_cuda_ternary.sh,
#  он лежит рядом; ниже — ключевые из записи)
export BITNET_GROUP_SIZE=128
export SLIDING_EVAL=1
export SLIDING_EVAL_STRIDE=16
export TEMP_SCALING=1

NPROC=$(nvidia-smi -L 2>/dev/null | grep -c '^GPU ' || echo 1)
echo "=== Плечо: $ARM (FP_STORAGE=$FP_STORAGE), seed=$SEED, GPU=$NPROC ==="
torchrun --standalone --nproc_per_node="$NPROC" train_gpt_cuda_gf8.py 2>&1 | tee "log_${RUN_ID}.txt"

# Итог: grep финального val_bpb
grep -E "val.*bpb|bpb.*val" "log_${RUN_ID}.txt" | tail -5
