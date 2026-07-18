# testB_realweights.py — PTQ ΔBPB на РЕАЛЬНЫХ весах микро-LM по классам бит.
# Все плечи per-row scaled. [измерено — микро-масштаб CPU], seed=20260718.
# Вопрос: какой сплит берёт класс на реальных LM-весах (не синтетике).
import numpy as np, math, json, os, sys, time
import torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gfplus_quant import phi_split, scaled_qd, sqnr_db

sys.path.insert(0, "/home/user/workspace/research")
CKPT = "/home/user/workspace/research/gfplus_line/microlm_fp32.npz"

# --- обучение (реюз test2-харнесса) или загрузка чекпоинта ---
rng = np.random.default_rng(20260718)
path = "/tmp/tinyshakespeare.txt"
if not os.path.exists(path):
    import urllib.request
    urllib.request.urlretrieve(
        "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt", path)
text = open(path, "rb").read()
vocab = sorted(set(text)); V = len(vocab)
stoi = {c: i for i, c in enumerate(vocab)}
ids = np.array([stoi[c] for c in np.frombuffer(text, np.uint8)], np.int32)
n = len(ids); split = int(n * 0.9)
train, val = ids[:split], ids[split:]
K, D, Hd, STEPS, B, LR = 8, 24, 256, 3000, 512, 3e-3

def fwd(p, X, Wq=None):
    W1 = Wq["W1"] if Wq else p["W1"]; W2 = Wq["W2"] if Wq else p["W2"]
    h0 = p["E"][X].reshape(len(X), -1)
    z1 = h0 @ W1 + p["b1"]; h1 = np.maximum(z1, 0)
    return h0, z1, h1, h1 @ W2 + p["b2"]

EVAL_IX = np.random.default_rng(7).integers(0, len(val) - K - 1, 40000)

def loss_bpb(p, Wq=None):
    X = np.stack([val[i:i+K] for i in EVAL_IX]); y = val[EVAL_IX + K]
    _, _, _, lg = fwd(p, X, Wq)
    lg = lg - lg.max(1, keepdims=True)
    ls = lg - np.log(np.exp(lg).sum(1, keepdims=True))
    return float(-ls[np.arange(len(y)), y].mean() / math.log(2))

if os.path.exists(CKPT):
    p_fp = {k: v for k, v in np.load(CKPT).items()}
else:
    p_fp = dict(
        E=(rng.standard_normal((V, D)) * 0.08).astype(np.float32),
        W1=(rng.standard_normal((K * D, Hd)) * (1 / math.sqrt(K * D))).astype(np.float32),
        b1=np.zeros(Hd, np.float32),
        W2=(rng.standard_normal((Hd, V)) * (1 / math.sqrt(Hd))).astype(np.float32),
        b2=np.zeros(V, np.float32))
    mom = {k: np.zeros_like(v) for k, v in p_fp.items()}
    for step in range(STEPS):
        ix = rng.integers(0, len(train) - K - 1, B)
        X = np.stack([train[i:i+K] for i in ix]); y = train[ix + K]
        h0, z1, h1, lg = fwd(p_fp, X)
        lg = lg - lg.max(1, keepdims=True)
        e = np.exp(lg); probs = e / e.sum(1, keepdims=True)
        dlg = probs; dlg[np.arange(len(y)), y] -= 1; dlg /= len(y)
        gW2 = h1.T @ dlg; gb2 = dlg.sum(0)
        dh1 = dlg @ p_fp["W2"].T; dz1 = dh1 * (z1 > 0)
        gW1 = h0.T @ dz1; gb1 = dz1.sum(0)
        dh0 = dz1 @ p_fp["W1"].T
        gE = np.zeros_like(p_fp["E"])
        np.add.at(gE, X.flatten(), dh0.reshape(len(X) * K, D))
        for k, g in zip(("W1", "b1", "W2", "b2", "E"), (gW1, gb1, gW2, gb2, gE)):
            mom[k] = 0.9 * mom[k] + g
            p_fp[k] -= LR * mom[k]
    np.savez(CKPT, **p_fp)

base = loss_bpb(p_fp)
print(f"fp32 baseline BPB = {base:.4f}")

# --- плечи по классам (все per-row scaled) ---
def arms_for(N):
    pe, pm, pb = phi_split(N)
    out = [(f"GF{N}+ e{pe}m{pm} (phi)", ("mf", dict(e=pe, m=pm, bias=pb)))]
    for e in (2, 3):
        if e != pe and e <= N - 2:
            m = N - 1 - e; b = 2 ** (e - 1) - 1
            out.append((f"e{e}m{m}", ("mf", dict(e=e, m=m, bias=b))))
    if N == 8:
        out.append(("fp8 e4m3", ("mf", dict(e=4, m=3, bias=7))))
    if N == 16:
        out.append(("fp16 e5m10", ("mf", dict(e=5, m=10, bias=15))))
        out.append(("bf16 e8m7", ("mf", dict(e=8, m=7, bias=127))))
    out.append((f"INT{N}", ("int", dict(bits=N))))
    if N == 4:
        out.append(("NF4", ("nf4", {})))
    return out

W1 = torch.from_numpy(p_fp["W1"].T.copy())  # per-row по выходным нейронам: строки = Hd
W2 = torch.from_numpy(p_fp["W2"].T.copy())

results = {"fp32_baseline": round(base, 4)}
for N in (4, 6, 8, 12, 16):
    print(f"\n=== Класс {N} бит (per-row scale, реальные веса) ===")
    print(f"{'fmt':<22}{'dBPB':>9}{'SQNR_W1':>9}{'SQNR_W2':>9}")
    rows = []
    for name, (kind, kw) in arms_for(N):
        q1 = scaled_qd(W1, kind, block=None, **kw)
        q2 = scaled_qd(W2, kind, block=None, **kw)
        s1, s2 = sqnr_db(W1, q1), sqnr_db(W2, q2)
        Wq = dict(W1=q1.T.numpy().astype(np.float32).copy(),
                  W2=q2.T.numpy().astype(np.float32).copy())
        d = loss_bpb(p_fp, Wq) - base
        rows.append(dict(fmt=name, dbpb=round(d, 4), sqnr_w1=round(s1, 2), sqnr_w2=round(s2, 2)))
        print(f"{name:<22}{d:>+9.4f}{s1:>9.2f}{s2:>9.2f}")
    results[N] = rows

with open("/home/user/workspace/research/gfplus_line/testB_results.json", "w") as f:
    json.dump(results, f, indent=1)
print("\nsaved testB_results.json")
