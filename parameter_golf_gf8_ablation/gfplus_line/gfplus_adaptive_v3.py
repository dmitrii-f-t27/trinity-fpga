# gfplus_adaptive_v3.py — GF+A v3: ВЕ��ТОР 2 — downstream-aware метрика выбора кармана.
# [измерено — SW proxy, CPU]. Аддитивно к v1/v2 (сохранены).
#
# ПРОБЛЕМА v1/v2 (инв. №15/№17): карман выбирается argmin по ЧИСТОМУ MSE весов
#   err = Σ (w - q(w))^2.
# Но downstream-ошибка слоя (что реально портит модель) = ошибка ВЫХОДА:
#   ||W x - q(W) x||^2 = Σ_i (Σ_j ΔW_ij x_j)^2.
# При калибровочном наборе активаций X (столбцы j) вклад ошибки веса W_ij взвешен
#   диагональю H_jj = Σ_samples x_j^2  (Хатчинсон-диагональ Гессиана слоя, как в OBQ/GPTQ).
# Поэтому downstream-aware выбор кармана = argmin по ВЗВЕШЕННОМУ MSE:
#   err_row_i = Σ_j H_jj * (W_ij - q(W_ij))^2 .
# Это метод «важности столбца» из OBQ (Hassibi) / GPTQ (Frantar) — второй-порядковый
# суррогат downstream-loss, НЕ полный Гессиан (диагональное приближение).
#
# Три под-направления вектора 2 (реализованы здесь + в testE_v3.py):
#   2а — sensitivity-выбор кармана (эта функция, metric='hess');
#   2б — сверка downstream-BPB/выходной-SQNR при MSE-выборе vs sensitivity-выборе;
#   2в — абляция «окупается ли sensitivity-выбор» (порог значимости 0.005 BPB).
import torch
from gfplus_adaptive_v2 import pockets_for_v2, _qd_pocket, e8m0_scale


def hutchinson_diag_from_acts(X):
    """Диагональ Гессиана слоя W (по входам j) через калибровочные активации.
    X: [n_samples, C_in]. H_jj = mean_s x_{s,j}^2  (масштаб не важен для argmin).
    Возвращает вектор весов важности длины C_in (>=0)."""
    X = X.double()
    return (X * X).mean(dim=0).clamp(min=1e-12)   # [C_in]


def gfplus_a_v3(x, N, hess_diag=None, metric="mse", group_K=1, scale_mode="e8m0",
                return_choice=False):
    """GF+A v3 с выбором downstream-aware.
    x: [R, C] веса слоя (R=out, C=in).
    hess_diag: [C] диагональ важности входов (H_jj). Нужна при metric='hess'.
    metric: 'mse' (как v2, невзвешенный) или 'hess' (взвешенный H_jj = downstream-суррогат).
    """
    x = x.double()
    R, C = x.shape
    pockets = pockets_for_v2(N)
    if scale_mode == "e8m0":
        amax = x.abs().amax(dim=-1, keepdim=True).clamp(min=1e-12)
        s = e8m0_scale(amax)
        xin = x / s
    else:
        s = torch.ones(R, 1, dtype=x.dtype)
        xin = x
    cands = [_qd_pocket(xin, k, kw) for _, k, kw in pockets]   # список [R,C]

    # весовой профиль по столбцам для метрики
    if metric == "hess":
        assert hess_diag is not None, "metric='hess' требует hess_diag"
        w = hess_diag.double().view(1, C)                     # [1,C]
    else:
        w = torch.ones(1, C, dtype=torch.double)

    # err[p, r] = Σ_j w_j * (xin - q_p)^2
    errs = torch.stack([ (w * (xin - q) ** 2).sum(dim=-1) for q in cands ])   # [P,R]

    if group_K > 1:
        P = errs.shape[0]
        pad = (-R) % group_K
        e = torch.nn.functional.pad(errs, (0, pad))
        eg = e.view(P, -1, group_K).sum(dim=-1)
        gch = eg.argmin(dim=0)
        choice = gch.repeat_interleave(group_K)[:R]
    else:
        choice = errs.argmin(dim=0)

    q = torch.stack(cands)[choice, torch.arange(R)]
    if scale_mode == "e8m0":
        q = q * s.squeeze(-1).unsqueeze(-1)
    if return_choice:
        return q, choice
    return q


def output_sqnr_db(W, Wq, X):
    """Честная downstream-метрика: SQNR ВЫХОДА слоя Y=WX^T (не весов).
    W,Wq: [R,C]; X: [n,C]. Возвращает дБ."""
    W = W.double(); Wq = Wq.double(); X = X.double()
    Y = X @ W.T
    Yq = X @ Wq.T
    p = (Y ** 2).mean()
    n = ((Y - Yq) ** 2).mean().clamp(min=1e-30)
    return float(10.0 * torch.log10(p / n))
