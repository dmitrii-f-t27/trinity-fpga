# testA_sweep.py — полный перебор сплитов (e,m) по классам бит в scaled-режиме.
# Вопрос: какой сплит РЕАЛЬНО берёт класс и совпадает ли он с φ-правилом.
# [измерено — SW proxy, CPU], seed=20260718.
import json
import torch
from gfplus_quant import phi_split, scaled_qd, sqnr_db

torch.manual_seed(20260718)
R, C = 512, 2048

DISTS = {}
DISTS["gauss"] = torch.randn(R, C)
g = torch.randn(R, C)
DISTS["heavy"] = g * g.abs() ** 1.5          # тяжёлые хвосты (как outlier-слои LM)
DISTS["uniform"] = torch.rand(R, C) * 2 - 1  # равномерное
# смешанные строки: 90% гаусс-строк + 10% строк с редкими выбросами (реалистичная LM-матрица)
mix = torch.randn(R, C)
idx = torch.randperm(R)[: R // 10]
mask = torch.rand(len(idx), C) < 0.01
mix[idx] = torch.where(mask, mix[idx] * 20, mix[idx])
DISTS["mixed_outlier"] = mix

CLASSES = [4, 6, 8, 12, 16]
BLOCK = None  # per-row (деплой-режим линейки); iso для всех конкурентов

results = {}
for N in CLASSES:
    phi_e, phi_m, phi_b = phi_split(N)
    rows = []
    # полный перебор сплитов e=0..N-2 (e=0 = fixed-point/int-подобный)
    for e in range(0, min(N - 1, 9)):  # e>8 не встречается в железе и переполняет float32
        m = N - 1 - e
        bias = 2 ** (e - 1) - 1 if e > 0 else 0
        tag = f"e{e}m{m}" + (" <- phi" if e == phi_e else "")
        r = {"fmt": tag, "e": e, "m": m}
        for dn, x in DISTS.items():
            q = scaled_qd(x, "mf", block=BLOCK, e=e, m=m, bias=bias)
            r[dn] = round(sqnr_db(x, q), 2)
        rows.append(r)
    # конкуренты класса
    comp = [("int", {"bits": N}, f"INT{N}")]
    if N == 4:
        comp.append(("nf4", {}, "NF4"))
    for kind, kw, name in comp:
        r = {"fmt": name, "e": None, "m": None}
        for dn, x in DISTS.items():
            q = scaled_qd(x, kind, block=BLOCK, **kw)
            r[dn] = round(sqnr_db(x, q), 2)
        rows.append(r)
    results[N] = rows

for N, rows in results.items():
    print(f"\n=== Класс {N} бит (per-row scale) — SQNR дБ ===")
    print(f"{'fmt':<14}" + "".join(f"{d:>14}" for d in DISTS))
    best = {d: max(r[d] for r in rows) for d in DISTS}
    for r in rows:
        line = f"{r['fmt']:<14}"
        for d in DISTS:
            star = "*" if r[d] == best[d] else " "
            line += f"{r[d]:>13.2f}{star}"
        print(line)

with open("testA_results.json", "w") as f:
    json.dump(results, f, indent=1)
print("\nsaved testA_results.json")
