# Vector 2 — GPU run on 29M (seed=42, RTX PRO 4500 Blackwell, torch 2.11.0+cu128)
[measured — GPU]. Script webterm_gfplus_v2select.py @ trinity-fpga main 23a5d2d0.
Model: 9L d=512 nhead=8 ffn=2048, 3000 steps FineWeb sp1024, final loss=3.696.
27 Linear layers >100k parameters. Downstream = SQNR of output Y=X·Wᵀ on VAL holdout,
pocket selection on calib-activations (Hessian diagonal H_jj=E[x_j²]).

## ΔSQNR summary (Hessian − MSE)
| bits | mean | median | better/worse/equal |
|---|---|---|---|
| 4  | +0.878 | +0.080 | 16/1/1 |
| 6  | +0.697 | +0.234 | 18/0/0 |
| 8  | +0.680 | +0.170 | 18/0/0 |

## Key pattern: the gain is localized in deep linear1 (FFN up-proj)
l.0.linear1: +0.008 (4b) → l.8.linear1: +3.102 (4b) / +2.155 (6b) / +1.825 (8b).
linear2 (down-proj, after activation) gains little (+0.01…+0.36) — activations are more uniform.
The gain GROWS with layer depth → mechanism = non-uniform importance of columns in deep FFNs.

## Conclusion (inverts the micro-LM)
Micro-LM (2 uniform layers): mean +0.055 dB, 7/3/2 = NEUTRAL.
29M (27 layers, heterogeneous): mean +0.68…+0.88 dB, 52/2/1 out of 54 cells = SIGNIFICANT.
→ downstream-aware (Hessian) selection PAYS OFF on heterogeneous weights; the magnitude depends
on the non-uniformity of the layer's input importance, not on the method. Hypothesis #18 confirmed.

## Boundaries
1 model/1 seed; downstream = SQNR of the linear layer output (a surrogate), NOT full model-BPB;
H_jj = diagonal approximation (OBQ/GPTQ). The BPB effect (whether the 2 bits/row header pays off)
has NOT been measured — SQNR ranks, but the Parameter Golf significance threshold = 0.005 BPB separately.
