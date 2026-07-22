# gfplus_adaptive_v2.py — GF+A v2: улучшения по векторам 1+3.
# [измерено — SW proxy, CPU] харнесс. Аддитивно к gfplus_adaptive.py (v1 сохранён).
#
# ВЕКТОР 1 — удешевить оверхед контейнера:
#   (1а) e8m0-scale (8 бит) вместо fp16 (16 бит) — экспонентный per-row scale (MX-стиль).
#        Для per-row absmax мантисса scale почти не нужна: absmax → ближайшая степень 2 вверх.
#   (1б) групповой заголовок: 1 выбор кармана на блок из K строк (карман редко меняется).
# ВЕКТОР 3 — живые карманы: заменить мёртвый φ-e3m4-слот на lns8 (логарифмический,
#        силён на тяжёлых хвостах, где линейные карманы проваливаются).
#
# Заголовок = 2 бита (4 кармана) на ГРУППУ из K строк; scale = 8 бит (e8m0) на строку.
import torch
from gfplus_quant import phi_split, scaled_qd, minifloat_qd, int_qd, nf4_qd

# ─────────────────────────── ВЕКТОР 3: lns8-карман ───────────────────────────
def lns_qd(x, bits, base_bits=None):
    """Логарифмический формат: знак + равномерная сетка по log2(|x|).
    Вход нормирован в [-1,1] (per-row scale уже применён снаружи). 0 маппится в 0.
    Сетка: 2^(bits-1)-1 уровней log2 в [LMIN, 0], LMIN = -(2^(bits-1)-1)*step."""
    x = x.double()
    L = 2 ** (bits - 1) - 1          # число ненулевых магнитуд-уровней
    a = x.abs()
    sgn = torch.sign(x)
    # динамический диапазон log2: от 0 (=|x|=1) вниз. step подобран под bits.
    LMAX = 0.0
    LMIN = -8.0                       # покрывает 8 порядков по основанию 2 (~2.4 десятичных)
    step = (LMAX - LMIN) / L
    la = torch.log2(a.clamp(min=2.0 ** LMIN))
    q_idx = torch.round((la - LMIN) / step).clamp(0, L)
    # idx=0 -> самый малый уровень; но истинный ноль обрабатываем отдельно
    mag = 2.0 ** (LMIN + q_idx * step)
    mag = torch.where(a < 2.0 ** (LMIN - 1), torch.zeros_like(mag), mag)
    return sgn * mag.clamp(max=1.0)


def scaled_lns(x, bits, block=None):
    x = x.double()
    amax = x.abs().amax(dim=-1, keepdim=True).clamp(min=1e-12)
    return lns_qd(x / amax, bits) * amax


# ─────────────────────── ВЕКТОР 1а: e8m0 (8-бит) scale ───────────────────────
def e8m0_scale(amax):
    """Квантует per-row scale в e8m0 (степень двойки, 8-бит экспонента, bias 127).
    Округление ВВЕРХ до ближайшей 2^k, чтобы не клиппить absmax."""
    k = torch.ceil(torch.log2(amax.clamp(min=1e-30)))
    k = torch.clamp(k, -127, 128)          # 8-бит экспонента e8m0
    return 2.0 ** k


# ─────────────────────── каталог карманов v2 (живые 4) ───────────────────────
def pockets_for_v2(N):
    """v2: φ-сплит, e2, INT, и вместо мёртвого φ-e3m4 → lns (для N>=6).
    N=4 сохраняет NF4 (доминирует на весах)."""
    pe, pm, pb = phi_split(N)
    out = [(f"phi_e{pe}m{pm}", "mf", dict(e=pe, m=pm, bias=pb))]
    if 2 <= N - 2:
        out.append((f"e2m{N-3}", "mf", dict(e=2, m=N - 3, bias=1)))
    out.append((f"int{N}", "int", dict(bits=N)))
    if N == 4:
        out.append(("nf4", "nf4", {}))
    else:
        out.append((f"lns{N}", "lns", dict(bits=N)))   # ВЕКТОР 3: живой 4-й слот
    return out[:4]


def _qd_pocket(x, kind, kw):
    if kind == "lns":
        return scaled_lns(x, kw["bits"])
    return scaled_qd(x, kind, block=None, **kw)


# ───────────────────────── GF+A v2 (per-group header) ─────────────────────────
def gfplus_a_v2(x, N, group_K=1, scale_mode="fp16", return_choice=False):
    """GF+A v2.
    group_K: строк на один общий выбор кармана (векгор 1б). K=1 = как v1.
    scale_mode: 'fp16' (16 бит) или 'e8m0' (8 бит, вектор 1а)."""
    x = x.double()
    R = x.shape[0]
    pockets = pockets_for_v2(N)
    # применяем e8m0-scale ДО выбора кармана (общий контейнерный scale)
    if scale_mode == "e8m0":
        amax = x.abs().amax(dim=-1, keepdim=True).clamp(min=1e-12)
        s = e8m0_scale(amax)
        xin = x / s
    else:
        s = torch.ones(R, 1, dtype=x.dtype)
        xin = x
    cands = [_qd_pocket(xin, k, kw) for _, k, kw in pockets]   # каждый сам делает per-row scale
    errs = torch.stack([((xin - q) ** 2).sum(dim=-1) for q in cands])   # [P,R]
    if group_K > 1:
        P = errs.shape[0]
        pad = (-R) % group_K
        e = torch.nn.functional.pad(errs, (0, pad))            # [P, R+pad]
        eg = e.view(P, -1, group_K).sum(dim=-1)                # [P, G] сумма ошибок по группе
        gch = eg.argmin(dim=0)                                 # [G]
        choice = gch.repeat_interleave(group_K)[:R]            # broadcast на строки
    else:
        choice = errs.argmin(dim=0)
    q = torch.stack(cands)[choice, torch.arange(R)] * (s.squeeze(-1).unsqueeze(-1) if scale_mode == "e8m0" else 1.0)
    if return_choice:
        return q, choice
    return q


def overhead_bpe_v2(x, N, group_K=1, scale_mode="fp16"):
    """Оверхед бит/элемент: заголовок 2/(K*C) + scale (16 или 8)/C."""
    C = x.shape[1]
    hdr = 2.0 / (group_K * C)
    sc = (8.0 if scale_mode == "e8m0" else 16.0) / C
    return hdr + sc
