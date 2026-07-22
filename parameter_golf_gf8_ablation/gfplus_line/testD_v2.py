# testD_v2.py — GF+A v1 vs v2 (векторы 1+3). Честная таблица: SQNR + ΔBPB + ОВЕРХЕД.
# Ключевой вопрос: окупается ли адаптив, когда учтён оверхед контейнера (заголовок+scale)?
# [измерено — SW proxy, CPU], seed=20260722.
import numpy as np, math, json, os, sys
import torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gfplus_quant import phi_split, scaled_qd, sqnr_db
from gfplus_adaptive import gfplus_a, pockets_for
from gfplus_adaptive_v2 import gfplus_a_v2, pockets_for_v2, overhead_bpe_v2, scaled_lns

torch.manual_seed(20260722)
R, C = 512, 2048
DISTS = {"gauss": torch.randn(R, C)}
g = torch.randn(R, C); DISTS["heavy"] = g * g.abs() ** 1.5
DISTS["uniform"] = torch.rand(R, C) * 2 - 1
mix = torch.randn(R, C)
idx = torch.randperm(R)[: R // 10]
mask = torch.rand(len(idx), C) < 0.01
mix[idx] = torch.where(mask, mix[idx] * 20, mix[idx])
DISTS["mixed_outlier"] = mix

print("=== ВЕКТОР 3: живой ли lns-карман? (синтетика, SQNR дБ) ===")
for N in (6, 8):
    print(f"\n--- Класс {N} бит: карманы v2 = {[p[0] for p in pockets_for_v2(N)]}")
    for dn, x in DISTS.items():
        _, ch = gfplus_a_v2(x, N, return_choice=True)
        cnt = torch.bincount(ch, minlength=4).tolist()
        pk = [p[0] for p in pockets_for_v2(N)]
        chs = ", ".join(f"{p}:{c}" for p, c in zip(pk, cnt) if c)
        print(f"  {dn:<14} выбор: {chs}")

# ── реальные веса микро-LM: v1 vs v2, ΔBPB с учётом оверхеда ──
CKPT = "/home/user/workspace/research/gfplus_line/microlm_fp32.npz"
p_fp = {k: v for k, v in np.load(CKPT).items()}
text = open("/tmp/tinyshakespeare.txt", "rb").read()
vocab = sorted(set(text)); stoi = {c: i for i, c in enumerate(vocab)}
ids = np.array([stoi[c] for c in np.frombuffer(text, np.uint8)], np.int32)
val = ids[int(len(ids) * 0.9):]
KW = 8
EVAL_IX = np.random.default_rng(7).integers(0, len(val) - KW - 1, 40000)

def loss_bpb(Wq=None):
    X = np.stack([val[i:i+KW] for i in EVAL_IX]); y = val[EVAL_IX + KW]
    W1 = Wq["W1"] if Wq else p_fp["W1"]; W2 = Wq["W2"] if Wq else p_fp["W2"]
    h0 = p_fp["E"][X].reshape(len(X), -1)
    h1 = np.maximum(h0 @ W1 + p_fp["b1"], 0)
    lg = h1 @ W2 + p_fp["b2"]; lg = lg - lg.max(1, keepdims=True)
    ls = lg - np.log(np.exp(lg).sum(1, keepdims=True))
    return float(-ls[np.arange(len(y)), y].mean() / math.log(2))

base = loss_bpb()
W1 = torch.from_numpy(p_fp["W1"].T.copy()); W2 = torch.from_numpy(p_fp["W2"].T.copy())
print(f"\n=== РЕАЛЬНЫЕ ВЕСА микро-LM (fp32 BPB={base:.4f}), W1 shape={tuple(W1.shape)} ===")

def eval_variant(fn):
    q1 = fn(W1); q2 = fn(W2)
    Wq = dict(W1=q1.T.numpy().astype(np.float32).copy(), W2=q2.T.numpy().astype(np.float32).copy())
    return loss_bpb(Wq) - base, sqnr_db(W1, q1), sqnr_db(W2, q2)

res = {"fp32_baseline": round(base, 4)}
for N in (4, 6, 8):
    print(f"\n--- Класс {N} бит (оверхед в бит/элемент при C={W1.shape[1]}) ---")
    print(f"{'вариант':<26}{'dBPB':>9}{'SQNR_W1':>9}{'ovh_bpe':>9}{'эфф.бит':>9}")
    rows = []
    variants = [
        ("v1 (fp16 scale, K=1)", lambda x: gfplus_a(x, N), 1, "fp16"),
        ("v2 e8m0 scale, K=1",   lambda x: gfplus_a_v2(x, N, 1, "e8m0"), 1, "e8m0"),
        ("v2 e8m0 scale, K=8",   lambda x: gfplus_a_v2(x, N, 8, "e8m0"), 8, "e8m0"),
        ("v2 e8m0 scale, K=32",  lambda x: gfplus_a_v2(x, N, 32, "e8m0"), 32, "e8m0"),
    ]
    for name, fn, K, sm in variants:
        d, s1, s2 = eval_variant(fn)
        ovh = overhead_bpe_v2(W1, N, K, sm)
        eff = N + ovh
        print(f"{name:<26}{d:>+9.4f}{s1:>9.2f}{ovh:>9.4f}{eff:>9.3f}")
        rows.append(dict(variant=name, dbpb=round(d, 4), sqnr_w1=round(s1, 2),
                         ovh_bpe=round(ovh, 4), eff_bits=round(eff, 3)))
    res[N] = rows

json.dump(res, open("/home/user/workspace/research/gfplus_line/testD_v2_results.json", "w"), indent=1)
print("\nsaved testD_v2_results.json")
