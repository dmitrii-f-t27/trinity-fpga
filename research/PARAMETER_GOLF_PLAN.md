# OpenAI Parameter Golf — Rules + Trinity Entry Plan

## Правила хакатона

| Параметр | Значение |
|----------|---------|
| **Артефакт** | ≤ 16MB (десятичных, не MiB) |
| **Обучение** | ≤ 10 минут на 8×H100 |
| **Оценка** | ≤ 10 минут на 8×H100 |
| **Метрика** | BPB (bits per byte) на FineWeb validation |
| **Содержимое** | code bytes + compressed model bytes |
| **Без external downloads** во время eval |
| **TTT разрешён**: только на уже оценённых токенах |

## Текущий лидерборд (top 5)

| Rank | Score (BPB) | Author | Ключевая техника |
|------|------------|--------|-----------------|
| 1 | **1.0611** | codemath3000 | SmearGate + LQER + SparseAttnGate + lrzip |
| 2 | 1.0614 | aquariouseworkman | SmearGate + LQER + Phased TTT |
| 3 | 1.0634 | nprime06 | PolarNS + SparseAttnGate + FusedCE |
| 4 | 1.0645 | dexhunter | CaseOps + SmearGate/LoRA-TTT |
| 5 | 1.0655 | dexhunter | SP8192 + CaseOps + GatedAttn + QuantGate |
| — | 1.1570 | Ciprian-Florin Ifrim | **Ternary quantization** (73.7M → {-1,0,+1}) |
| — | 1.2244 | Baseline | Naive 9L 512dim |

## Где Trinity может выиграть

### Уникальные преимущества GF16+:

1. **Точный Quire accumulation** → меньше quantization noise → лучше BPB
2. **φ-anchored learning rate** (INV-8: lr=0.004=α_φ/φ³) → Coq-proven optimal band
3. **GF16 = 16-bit at 505 LUT** → больше моделей в 16MB
4. **Ternary MAC = 52 LUT** → BitNet b1.58 weights на FPGA

### Конкретный план для submission:

**Архитектура:**
- 11 layers, d_model=512, MLP 3× (как у топ-5)
- **Веса: GF16 quantization** (16-bit, φ-rule E=6 M=9)
- **Embeddings: int7 GPTQ** (как у dexhunter)
- **Attention: SmearGate** (как у топ-1)
- **Optimizer: Muon 0.97** (как у #12)
- **TTT: score-first LoRA** (legal, как у топ-5)
- **Сжатие: lrzip** (как у #1)
- **Quire: GF16+ accumulation в optimizer state**

**Оценка BPB при GF16 (из IGLA RACE):**
- gf16 × rmsprop local bigram: BPB 5.9925 (rank #2 из 20 форматов)
- gf16 × adamw matrix h=96: BPB 6.975 (rank #4)
- gf256 × adamw champion: BPB 2.5719 (но gf256 = 256-бит!)

**16MB budget при GF16:**
- GF16 = 2 bytes/param → 16MB / 2 = 8M parameters
- С int7 GPTQ: ~4.5 bytes/param → ~3.5M parameters
- С ternary: 2 bits/param → 64M parameters (!)

### Что нужно сделать:

1. Клонировать `gHashTag/parameter-golf-trinity`
2. Реализовать GF16+ QAT в `train_gpt.py`
3. Запустить на H100 (через compute grant или Colab)
4. Измерить BPB на FineWeb validation
5. Submit PR в `openai/parameter-golf`

### Связь с нашим исследованием

| Наш результат | Применение в Parameter Golf |
|--------------|---------------------------|
| GF16+ = 100% gradient survival | Меньше quantization noise → ниже BPB |
| BF16 теряет 93% updates | НЕ использовать BF16 |
| φ-rule lr=0.004 | Оптимальный LR (Coq INV-8) |
| GF16+ Quire на кремнии | Доказано на AX7203 |
| Golden Ruler | Подбор формата под задачу |
