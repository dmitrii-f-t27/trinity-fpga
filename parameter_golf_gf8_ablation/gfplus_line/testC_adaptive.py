# testC_adaptive.py — GF+A против всех фиксированных конкурентов класса.
# Синтетика (4 распределения) + реальные веса микро-LM (ΔBPB).
# [измерено — SW proxy, CPU], seed=20260718.
import numpy as np, math, json, os, sys
import torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gfplus_quant import phi_split, scaled_qd, sqnr_db
from gfplus_adaptive import gfplus_a, pockets_for

torch.manual_seed(20260718)
R, C = 512, 2048
DISTS = {"gauss": torch.randn(R, C)}
g = torch.randn(R, C); DISTS["heavy"] = g * g.abs() ** 1.5
DISTS["uniform"] = torch.rand(R, C) * 2 - 1
mix = torch.randn(R, C)
idx = torch.randperm(R)[: R // 10]
mask = torch.rand(len(idx), C) < 0.01
mix[idx] = torch.where(mask, mix[idx] * 20, mix[idx])
DISTS["mixed_outlier"] = mix

def fixed_arms(N):
    out = [(n, k, kw) for n, k, kw in pockets_for(N)]
    # добавить стандартных конкурентов, которых нет среди карманов
    if N == 8:
        out += [("fp8_e4m3", "mf", dict(e=4, m=3, bias=7)),
                ("fp8_e5m2", "mf", dict(e=5, m=2, bias=15))]
    if N == 16:
        out += [("fp16_e5m10", "mf", dict(e=5, m=10, bias=15)),
                ("bf16_e8m7", "mf", dict(e=8, m=7, bias=127))]
    if N == 6:
        out += [("fp6_e3m2", "mf", dict(e=3, m=2, bias=3))]
    return out

print("=== СИНТЕТИКА: GF+A vs фиксированные (SQNR дБ, per-row scale) ===")
resA = {}
for N in (4, 6, 8, 12, 16):
    rows = []
    for name, kind, kw in fixed_arms(N):
        r = {"fmt": name}
        for dn, x in DISTS.items():
            r[dn] = round(sqnr_db(x, scaled_qd(x, kind, block=None, **kw)), 2)
        rows.append(r)
    r = {"fmt": f"GF{N}+A"}
    for dn, x in DISTS.items():
        r[dn] = round(sqnr_db(x, gfplus_a(x, N)), 2)
    rows.append(r)
    resA[N] = rows
    print(f"\n--- Класс {N} бит ---")
    print(f"{'fmt':<14}" + "".join(f"{d:>14}" for d in DISTS))
    best = {d: max(rr[d] for rr in rows) for d in DISTS}
    for rr in rows:
        line = f"{rr['fmt']:<14}"
        for d in DISTS:
            line += f"{rr[d]:>13.2f}{'*' if rr[d] == best[d] else ' '}"
        print(line)

# --- реальные веса микро-LM: SQNR + ΔBPB ---
CKPT = "/home/user/workspace/research/gfplus_line/microlm_fp32.npz"
p_fp = {k: v for k, v in np.load(CKPT).items()}
path = "/tmp/tinyshakespeare.txt"
text = open(path, "rb").read()
vocab = sorted(set(text)); V = len(vocab)
stoi = {c: i for i, c in enumerate(vocab)}
ids = np.array([stoi[c] for c in np.frombuffer(text, np.uint8)], np.int32)
val = ids[int(len(ids) * 0.9):]
K = 8
EVAL_IX = np.random.default_rng(7).integers(0, len(val) - K - 1, 40000)

def loss_bpb(Wq=None):
    X = np.stack([val[i:i+K] for i in EVAL_IX]); y = val[EVAL_IX + K]
    W1 = Wq["W1"] if Wq else p_fp["W1"]; W2 = Wq["W2"] if Wq else p_fp["W2"]
    h0 = p_fp["E"][X].reshape(len(X), -1)
    h1 = np.maximum(h0 @ W1 + p_fp["b1"], 0)
    lg = h1 @ W2 + p_fp["b2"]
    lg = lg - lg.max(1, keepdims=True)
    ls = lg - np.log(np.exp(lg).sum(1, keepdims=True))
    return float(-ls[np.arange(len(y)), y].mean() / math.log(2))

base = loss_bpb()
W1 = torch.from_numpy(p_fp["W1"].T.copy()); W2 = torch.from_numpy(p_fp["W2"].T.copy())
print(f"\n=== РЕАЛЬНЫЕ ВЕСА микро-LM (fp32 BPB={base:.4f}) ===")
resB = {"fp32_baseline": round(base, 4)}
for N in (4, 6, 8):
    rows = []
    arms = fixed_arms(N) + [("ADAPTIVE", None, None)]
    print(f"\n--- Класс {N} бит ---")
    print(f"{'fmt':<14}{'dBPB':>9}{'SQNR_W1':>9}{'SQNR_W2':>9}{'выбор карманов W1':>24}")
    for name, kind, kw in arms:
        if kind is None:
            q1, ch1 = gfplus_a(W1, N, return_choice=True)
            q2, _ = gfplus_a(W2, N, return_choice=True)
            pk = [p[0] for p in pockets_for(N)]
            cnt = torch.bincount(ch1, minlength=len(pk)).tolist()
            chs = ",".join(f"{p}:{c}" for p, c in zip(pk, cnt) if c)
            name = f"GF{N}+A"
        else:
            q1 = scaled_qd(W1, kind, block=None, **kw)
            q2 = scaled_qd(W2, kind, block=None, **kw)
            chs = ""
        Wq = dict(W1=q1.T.numpy().astype(np.float32).copy(),
                  W2=q2.T.numpy().astype(np.float32).copy())
        d = loss_bpb(Wq) - base
        s1, s2 = sqnr_db(W1, q1), sqnr_db(W2, q2)
        rows.append(dict(fmt=name, dbpb=round(d, 4), sqnr_w1=round(s1, 2), sqnr_w2=round(s2, 2), pockets=chs))
        print(f"{name:<14}{d:>+9.4f}{s1:>9.2f}{s2:>9.2f}{chs:>24}")
    resB[N] = rows

json.dump({"synthetic": resA, "real": resB},
          open("/home/user/workspace/research/gfplus_line/testC_results.json", "w"), indent=1)
print("\nsaved testC_results.json")
