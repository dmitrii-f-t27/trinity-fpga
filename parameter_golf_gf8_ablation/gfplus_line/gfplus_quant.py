# gfplus_quant.py — линейка GF+ и конкуренты, генерический квантизатор
# [измерено — SW proxy, CPU] харнесс; seed фиксируется в бенчмарках.
# Все форматы в scaled-режиме: absmax -> max формата, гранулярность per-row или per-block.
import torch

PHI2 = ((1 + 5**0.5) / 2) ** 2


def phi_split(N):
    e = round((N - 1) / PHI2)
    m = N - 1 - e
    bias = 2 ** (e - 1) - 1 if e > 0 else 0
    return e, m, bias


def minifloat_qd(x, e, m, bias):
    """Generic minifloat quant-dequant: знак+e+m, RNE, денормалы, fn-насыщение (без inf/nan)."""
    x = x.double()
    if e == 0:  # чистый fixed-point с m битами мантиссы (int-подобный)
        step = 2.0 ** (-m)
        mx = (2**m - 1) * step
        return torch.clamp(torch.round(x / step) * step, -mx, mx)
    EMIN = 1 - bias
    EMAX = (1 << e) - 1 - bias
    MAXN = 2.0**EMAX * (2 - 2.0**-m)
    a = x.abs()
    sgn = torch.sign(x)
    # экспонента значения, clamp в [EMIN, EMAX]
    ex = torch.floor(torch.log2(torch.clamp(a, min=2.0 ** (EMIN - m - 1))))
    ex = torch.clamp(ex, min=EMIN, max=EMAX)
    # шаг кванта: денормалы (a < 2^EMIN) имеют шаг 2^(EMIN-m)
    step = torch.where(a < 2.0**EMIN, torch.full_like(a, 2.0 ** (EMIN - m)), 2.0 ** (ex - m))
    q = torch.round(a / step) * step  # RNE у torch.round (banker's) — единый для всех форматов
    # после округления вверх могла смениться экспонента — пере-clamp к max
    q = torch.clamp(q, max=MAXN)
    return sgn * q


def int_qd(x, bits):
    """Симметричный int: уровни -(2^(b-1)-1)..+(2^(b-1)-1); вход уже в [-max,max] масштаба."""
    L = 2 ** (bits - 1) - 1
    return torch.round(torch.clamp(x, -1.0, 1.0) * L) / L


NF4_LEVELS = torch.tensor([
    -1.0, -0.6961928009986877, -0.5250730514526367, -0.39491748809814453,
    -0.28444138169288635, -0.18477343022823334, -0.09105003625154495, 0.0,
    0.07958029955625534, 0.16093020141124725, 0.24611230194568634,
    0.33791524171829224, 0.44070982933044434, 0.5626170039176941,
    0.7229568362236023, 1.0])


def nf4_qd(x):
    """NF4 (bitsandbytes codebook), вход нормирован в [-1,1]."""
    lv = NF4_LEVELS.to(x.dtype)
    idx = torch.argmin((x.unsqueeze(-1) - lv).abs(), dim=-1)
    return lv[idx]


def _block_view(x, block):
    r, c = x.shape
    pad = (-c) % block
    if pad:
        x = torch.nn.functional.pad(x, (0, pad))
    return x.view(r, -1, block), c, pad


def scaled_qd(x, kind, block=None, **kw):
    """Масштабированный quant-dequant. kind: 'mf' (e,m,bias), 'int' (bits), 'nf4'.
    block=None -> per-row absmax; block=int -> per-block absmax."""
    x = x.double()
    if block is None:
        g = x
        amax = g.abs().amax(dim=-1, keepdim=True).clamp(min=1e-12)
    else:
        g, c, pad = _block_view(x, block)
        amax = g.abs().amax(dim=-1, keepdim=True).clamp(min=1e-12)
    if kind == "mf":
        e, m, bias = kw["e"], kw["m"], kw["bias"]
        if e == 0:
            tgt = 1.0
        else:
            tgt = 2.0 ** ((1 << e) - 1 - bias) * (2 - 2.0 ** -m)
        scale = amax / tgt
        q = minifloat_qd(g / scale, e, m, bias) * scale
    elif kind == "int":
        scale = amax
        q = int_qd(g / scale, kw["bits"]) * scale
    elif kind == "nf4":
        scale = amax
        q = nf4_qd(g / scale) * scale
    else:
        raise ValueError(kind)
    if block is not None:
        q = q.view(x.shape[0], -1)[:, :x.shape[1] if not pad else -pad] if pad else q.view(x.shape)
        if pad:
            q = q[:, :c]
    return q


def sqnr_db(x, q):
    num = (x.double() ** 2).sum()
    den = ((x.double() - q.double()) ** 2).sum().clamp(min=1e-30)
    return float(10 * torch.log10(num / den))
