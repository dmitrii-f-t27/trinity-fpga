# testE_v3.py — ВЕКТОР 2: downstream-aware выбор кармана GF+A.
# [измерено — SW proxy, CPU]. seed=20260722.
# Честная схема: выбор кармана делаем ДВУМЯ метриками (MSE весов vs Hessian-взвеш.),
# а СРАВНИВАЕМ обе по ОДНОЙ downstream-метрике — SQNR ВЫХОДА слоя Y=X·W^T на калибр. данных.
# Это ловит именно то, что MSE весов игнорирует: важность столбца (входного признака).
import numpy as np, torch, json
from gfplus_adaptive_v3 import gfplus_a_v3, hutchinson_diag_from_acts, output_sqnr_db

torch.manual_seed(20260722); np.random.seed(20260722)
p = np.load("/home/user/workspace/research/gfplus_line/microlm_fp32.npz")
E, W1, W2 = p["E"], p["W1"], p["W2"]          # E:[65,24] W1:[192,256] W2:[256,65]

# ── калибровочные активации: прогон реального текста через микро-LM ──
txt = open("/tmp/tinyshakespeare.txt").read()[:20000]
chars = sorted(set(txt)); stoi = {c: i for i, c in enumerate(chars)}
CTX = W1.shape[0] // E.shape[1]               # 192/24 = 8 символов контекста
ids = np.array([stoi.get(c, 0) % E.shape[0] for c in txt])
n = 2000
starts = np.random.randint(0, len(ids) - CTX - 1, size=n)
Xctx = np.stack([ids[s:s + CTX] for s in starts])          # [n, CTX]
h0 = E[Xctx].reshape(n, -1).astype(np.float64)             # [n,192] вход W1
z1 = h0 @ W1 + p["b1"]; h1 = np.maximum(z1, 0).astype(np.float64)   # [n,256] вход W2

layers = {
    "W1 (192->256)": (torch.tensor(W1.T), torch.tensor(h0)),   # W:[out=256,in=192], X:[n,192]
    "W2 (256->65)":  (torch.tensor(W2.T), torch.tensor(h1)),   # W:[out=65,in=256],  X:[n,256]
}

def bpe_over(W, N, C, group_K, scale_mode):
    hdr = 2.0 / (group_K * C); sc = (8.0 if scale_mode == "e8m0" else 16.0) / C
    return N + hdr + sc

report = {}
print("=== ВЕКТОР 2: MSE-выбор vs Hessian-выбор (downstream SQNR выхода слоя) ===")
print("порог значимости Parameter Golf = 0.005 BPB; SQNR — выход Y=X·W^T\n")
for lname, (W, X) in layers.items():
    C = W.shape[1]
    hess = hutchinson_diag_from_acts(X)                     # [C] H_jj
    print(f"--- {lname}  (C_in={C}, n_calib={X.shape[0]}) ---")
    print(f"{'N':>3} {'K':>3}  {'SQNR_mse':>9} {'SQNR_hess':>10} {'ΔSQNR':>7}  {'выбор изменился, строк':>22}")
    report[lname] = {}
    for N in (4, 6, 8):
        for K in (1, 8):
            q_mse, ch_mse = gfplus_a_v3(W, N, metric="mse", group_K=K,
                                        scale_mode="e8m0", return_choice=True)
            q_h, ch_h = gfplus_a_v3(W, N, hess_diag=hess, metric="hess", group_K=K,
                                    scale_mode="e8m0", return_choice=True)
            s_mse = output_sqnr_db(W, q_mse, X)
            s_h = output_sqnr_db(W, q_h, X)
            changed = int((ch_mse != ch_h).sum())
            print(f"{N:>3} {K:>3}  {s_mse:>9.3f} {s_h:>10.3f} {s_h - s_mse:>+7.3f}  {changed:>22}")
            report[lname][f"N{N}_K{K}"] = dict(sqnr_mse=s_mse, sqnr_hess=s_h,
                                               dsqnr=s_h - s_mse, changed=changed)
    print()

json.dump(report, open("testE_v3_results.json", "w"), indent=2)
print("saved testE_v3_results.json")
