# GF8 ablation of fp-pockets of the ternary model (Parameter Golf)

Prepared 18.07.2026. Hypothesis: in the Ifrim record
(`2026-03-24_74M_Ternary_UNet_FP8_10L_8192BPE_YaRN_NeoMuon`, val_bpb 1.1570)
~2.5M non-ternary parameters are stored and trained via FP8-QAT (e4m3, direct cast).
Replacing these pockets with **GF8 e3m4** (φ field-rule: e=3, m=4, bias=3) with per-row
scaling can improve the representational accuracy of the pockets. `[open hypothesis]`

## Files

| File | What it is |
|---|---|
| `gf8_quant.py` | GF8 e3m4: quant/dequant, encode/decode (uint8 + fp16 scale), STE. Unit-tests inside (`python3 gf8_quant.py`) — all passed on CPU 18.07.2026 |
| `patch_gf8.py` | Patcher: official `train_gpt_cuda_ternary.py` → `train_gpt_cuda_gf8.py` (5 anchors, aborts on ambiguity) |
| `train_gpt_cuda_gf8.py` | Ready patched script (syntax checked; functionally NOT run on GPU — no CUDA in the sandbox) |
| `run_gf8_ablation.sh` | Launch of three arms on 8×H100. **Before launch, copy the full env block from the original `run_cuda_ternary.sh`** — here only the key ones |
| `train_gpt_cuda_ternary.py`, `run_cuda_ternary.sh`, `setup.sh`, `requirements.txt` | Originals from the official record (raw.githubusercontent.com, main) |

## Ablation design (3 arms, identical seeds)

1. **fp8** — repro of the official record: e4m3 direct cast, no scale. Expected ≈1.157 bpb.
2. **fp8s** — control: e4m3 + per-row absmax scale. Separates the scaling effect from the format effect.
3. **gf8** — e3m4 + per-row absmax scale (same scaling, different field split).

Parameter Golf protocol: 3 seeds per arm, significance ≥0.005 nats. The fp8s↔gf8 difference = the
pure format effect.

## A-priori expectations `[measured — SW proxy, CPU]`

REPRESENTATIONAL error (not downstream bpb!) on N(0,1) and heavy tails:

| Mode | SQNR gaussian | SQNR heavy-tail |
|---|---|---|
| gf8_scaled | **37.6 dB** | **37.9 dB** |
| e4m3_scaled | 31.6 dB | 31.9 dB |
| e4m3_direct | 31.5 dB | 31.6 dB |

Honesty nuance: the previous measurement (loop 06.07.2026e, WITHOUT per-row scale) gave the opposite
sign (e4m3 ≈ 31 > GF8 ≈ 29 dB). **Per-row scaling flips the winner**: when the row range is narrow,
the wide exponent e4m3 sits idle and the extra mantissa bit of e3m4 decides (+6 dB). Transfer of the
+6 dB representation into Δbpb is NOT guaranteed — the pockets are small (2.5M/73.7M), QAT partially
compensates for the format error. A realistic outcome: Δbpb from ~0 to a small plus.
A negative result is also valuable — it is an honest point in the co-design matrix.

## Artifact overhead

GF8: +2 bytes of fp16-scale per matrix row. For pockets of ~2.5M parameters this is ≤ a few KB —
the headroom up to the 16,000,000-byte limit of the Ifrim record was 6,147 bytes; check
`stats["fp_bytes"]` after the first run (if it does not fit — switch to a per-tensor shared scale,
the fix is trivial).

## What has NOT been verified (boundaries)

- Functional run on GPU: no CUDA/flash_attn in the sandbox — the träin-script was checked
  only for syntax + unit-tests of the quant-module on CPU.
- torch.compile compatibility: the gf8 STE branch uses exp2/log2/round — compilable,
  but verify on the pod.
- Impact on speed: GF8 STE is more expensive than a direct e4m3 cast (a few tensor ops).
  Under a 10-min limit check whether it eats training steps.
