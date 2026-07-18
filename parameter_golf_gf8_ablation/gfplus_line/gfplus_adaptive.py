# gfplus_adaptive.py — GF+A: per-row адаптивный выбор кармана из φ-каталога.
# Идея = инвариант №15 (лучший формат = процедура ВЫБОРА): формат-контейнер,
# где каждая строка несёт 2-битный заголовок (какой карман) + fp16 scale.
# Карманы класса N: {φ-сплит, e2, e3, INT-сетка}; в классе 4 бит — {φ/INT, e2m1, NF4}.
# По построению per-row ошибка <= ошибки ЛЮБОГО одиночного кармана из набора.
import torch
from gfplus_quant import phi_split, scaled_qd

def pockets_for(N):
    pe, pm, pb = phi_split(N)
    seen, out = set(), []
    def add(name, kind, kw):
        key = (kind, tuple(sorted(kw.items())))
        if key not in seen:
            seen.add(key); out.append((name, kind, kw))
    add(f"phi_e{pe}m{pm}", "mf", dict(e=pe, m=pm, bias=pb))
    for e in (2, 3):
        if e <= N - 2:
            add(f"e{e}m{N-1-e}", "mf", dict(e=e, m=N - 1 - e, bias=2 ** (e - 1) - 1))
    add(f"int{N}", "int", dict(bits=N))
    if N == 4:
        add("nf4", "nf4", {})
    return out[:4]  # заголовок 2 бита -> максимум 4 кармана

def gfplus_a(x, N, return_choice=False):
    """GF+A quant-dequant: per-row absmax scale + per-row argmin-карман."""
    x = x.double()
    cands = []
    for _, kind, kw in pockets_for(N):
        cands.append(scaled_qd(x, kind, block=None, **kw))
    errs = torch.stack([((x - q) ** 2).sum(dim=-1) for q in cands])  # [P, R]
    choice = errs.argmin(dim=0)                                      # [R]
    q = torch.stack(cands)[choice, torch.arange(x.shape[0])]
    if return_choice:
        return q, choice
    return q

def overhead_bits_per_elem(x, N):
    """Оверхед контейнера: 2 бита заголовка + 16 бит scale на строку."""
    return (2 + 16) / x.shape[1]
