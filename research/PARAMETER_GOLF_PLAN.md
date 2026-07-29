# OpenAI Parameter Golf — Rules + Trinity Entry Plan

## Hackathon rules

| Parameter | Value |
|----------|---------|
| **Artifact** | ≤ 16MB (decimal, not MiB) |
| **Training** | ≤ 10 minutes on 8×H100 |
| **Evaluation** | ≤ 10 minutes on 8×H100 |
| **Metric** | BPB (bits per byte) on FineWeb validation |
| **Contents** | code bytes + compressed model bytes |
| **No external downloads** during eval |
| **TTT allowed**: only on already-evaluated tokens |

## Current leaderboard (top 5)

| Rank | Score (BPB) | Author | Key technique |
|------|------------|--------|-----------------|
| 1 | **1.0611** | codemath3000 | SmearGate + LQER + SparseAttnGate + lrzip |
| 2 | 1.0614 | aquariouseworkman | SmearGate + LQER + Phased TTT |
| 3 | 1.0634 | nprime06 | PolarNS + SparseAttnGate + FusedCE |
| 4 | 1.0645 | dexhunter | CaseOps + SmearGate/LoRA-TTT |
| 5 | 1.0655 | dexhunter | SP8192 + CaseOps + GatedAttn + QuantGate |
| — | 1.1570 | Ciprian-Florin Ifrim | **Ternary quantization** (73.7M → {-1,0,+1}) |
| — | 1.2244 | Baseline | Naive 9L 512dim |

## Where Trinity can win

### Unique advantages of GF16+:

1. **Exact Quire accumulation** → less quantization noise → better BPB
2. **φ-anchored learning rate** (INV-8: lr=0.004=α_φ/φ³) → Coq-proven optimal band
3. **GF16 = 16-bit at 505 LUT** → more models in 16MB
4. **Ternary MAC = 52 LUT** → BitNet b1.58 weights on FPGA

### Concrete plan for the submission:

**Architecture:**
- 11 layers, d_model=512, MLP 3× (like the top-5)
- **Weights: GF16 quantization** (16-bit, φ-rule E=6 M=9)
- **Embeddings: int7 GPTQ** (like dexhunter)
- **Attention: SmearGate** (like top-1)
- **Optimizer: Muon 0.97** (like #12)
- **TTT: score-first LoRA** (legal, like the top-5)
- **Compression: lrzip** (like #1)
- **Quire: GF16+ accumulation in optimizer state**

**BPB estimate at GF16 (from IGLA RACE):**
- gf16 × rmsprop local bigram: BPB 5.9925 (rank #2 of 20 formats)
- gf16 × adamw matrix h=96: BPB 6.975 (rank #4)
- gf256 × adamw champion: BPB 2.5719 (but gf256 = 256-bit!)

**16MB budget at GF16:**
- GF16 = 2 bytes/param → 16MB / 2 = 8M parameters
- With int7 GPTQ: ~4.5 bytes/param → ~3.5M parameters
- With ternary: 2 bits/param → 64M parameters (!)

### What needs to be done:

1. Clone `gHashTag/parameter-golf-trinity`
2. Implement GF16+ QAT in `train_gpt.py`
3. Run on H100 (via compute grant or Colab)
4. Measure BPB on FineWeb validation
5. Submit PR to `openai/parameter-golf`

### Connection with our research

| Our result | Application in Parameter Golf |
|--------------|---------------------------|
| GF16+ = 100% gradient survival | Less quantization noise → lower BPB |
| BF16 loses 93% of updates | Do NOT use BF16 |
| φ-rule lr=0.004 | Optimal LR (Coq INV-8) |
| GF16+ Quire on silicon | Proven on AX7203 |
| Golden Ruler | Format selection for the task |
