# testE_v3_holdout.py — вектор 2в: ЧЕСТНАЯ абляция с holdout.
# Выбор кармана (Hessian) считаем на CALIB-активациях, а downstream-SQNR оцениваем на
# НЕЗАВИСИМЫХ VAL-активациях. Иначе Hessian-выбор переобучается под калибр-набор и
# «выигрыш» = утечка. Это отвечает на вопрос «окупается ли sensitivity-выбор» честно.
import numpy as np, torch, json
from gfplus_adaptive_v3 import gfplus_a_v3, hutchinson_diag_from_acts, output_sqnr_db

torch.manual_seed(20260722); np.random.seed(20260722)
p = np.load("/home/user/workspace/research/gfplus_line/microlm_fp32.npz")
E, W1, W2 = p["E"], p["W1"], p["W2"]
txt = open("/tmp/tinyshakespeare.txt").read()
chars = sorted(set(txt)); stoi = {c: i for i, c in enumerate(chars)}
CTX = W1.shape[0] // E.shape[1]
ids = np.array([stoi.get(c, 0) % E.shape[0] for c in txt])

def acts(n, off):
    st = np.random.RandomState(off).randint(0, len(ids) - CTX - 1, size=n)
    Xc = np.stack([ids[s:s + CTX] for s in st])
    h0 = E[Xc].reshape(n, -1).astype(np.float64)
    z1 = h0 @ W1 + p["b1"]; h1 = np.maximum(z1, 0).astype(np.float64)
    return h0, h1

h0c, h1c = acts(4000, 1)      # calib
h0v, h1v = acts(4000, 999)    # val (независи��ый)
layers = {
    "W1 (192->256)": (torch.tensor(W1.T), torch.tensor(h0c), torch.tensor(h0v)),
    "W2 (256->65)":  (torch.tensor(W2.T), torch.tensor(h1c), torch.tensor(h1v)),
}

print("=== ВЕКТОР 2в: holdout-абляция (выбор на calib, оценка на VAL) ===")
print("Честный вопрос: обобщается ли Hessian-выигрыш на невиданные активации?\n")
rep = {}
for lname, (W, Xc, Xv) in layers.items():
    hess = hutchinson_diag_from_acts(Xc)
    print(f"--- {lname} ---")
    print(f"{'N':>3} {'K':>3}  {'val SQNR_mse':>12} {'val SQNR_hess':>13} {'ΔSQNR_val':>10}")
    rep[lname] = {}
    for N in (4, 6, 8):
        for K in (1, 8):
            q_mse = gfplus_a_v3(W, N, metric="mse", group_K=K, scale_mode="e8m0")
            q_h = gfplus_a_v3(W, N, hess_diag=hess, metric="hess", group_K=K, scale_mode="e8m0")
            sm = output_sqnr_db(W, q_mse, Xv)     # оценка на VAL
            sh = output_sqnr_db(W, q_h, Xv)
            print(f"{N:>3} {K:>3}  {sm:>12.3f} {sh:>13.3f} {sh - sm:>+10.3f}")
            rep[lname][f"N{N}_K{K}"] = dict(val_mse=sm, val_hess=sh, dval=sh - sm)
    print()
json.dump(rep, open("testE_v3_holdout_results.json", "w"), indent=2)
print("saved testE_v3_holdout_results.json")

# сводка: среднее ΔSQNR_val по всем ячейкам
alld = [c["dval"] for L in rep.values() for c in L.values()]
print(f"\nСреднее ΔSQNR_val (Hessian − MSE) по 12 ячейкам: {np.mean(alld):+.3f} дБ")
print(f"Медиана: {np.median(alld):+.3f} дБ; знак-баланс: "
      f"{sum(d>0 for d in alld)} лучше / {sum(d<0 for d in alld)} хуже / {sum(d==0 for d in alld)} равно")
