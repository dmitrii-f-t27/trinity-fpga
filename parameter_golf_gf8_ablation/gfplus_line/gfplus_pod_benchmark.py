# gfplus_pod_benchmark.py — САМОДОСТАТОЧНЫЙ бенчмарк линейки GF+ (φ-карманы + GF+A)
# [измерено — SW proxy] harness; adaptive = per-row argmin-карман, заголовок 2 бита/строку.
import torch
# gfplus_quant.py — линейка GF+ и конкуренты, генерический квантизатор
# [измерено — SW proxy, CPU] харнесс; seed фиксируется в бенчмарках.
# Все форматы в scaled-режиме: absmax -> max формата, гранулярность per-row или per-block.

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


# ================= MAIN: лидерборд GF+ по классам на реальном чекпоинте =================
# Использование на поде:
#   python3 gfplus_pod_benchmark.py /workspace/model.pt      # любой state_dict .pt
#   python3 gfplus_pod_benchmark.py --synthetic              # без чекпоинта
# Квантуются все 2D-тензоры >= 64x64 (веса линейных слоёв), per-row scale по dim=-1.
# Метрика: SQNR (дБ). Для BPB интегрировать q-функции в webterm_benchmark (drop-in torch).
import sys, glob, json

def fixed_arms(N):
    out = list(pockets_for(N))
    if N == 8:
        out += [("fp8_e4m3", "mf", dict(e=4, m=3, bias=7)),
                ("fp8_e5m2", "mf", dict(e=5, m=2, bias=15))]
    if N == 6:
        out += [("fp6_e3m2", "mf", dict(e=3, m=2, bias=3))]
    if N == 16:
        out += [("fp16_e5m10", "mf", dict(e=5, m=10, bias=15)),
                ("bf16_e8m7", "mf", dict(e=8, m=7, bias=127))]
    return out

def collect_mats(sd):
    mats = {}
    for k, v in sd.items():
        if hasattr(v, "dim") and v.dim() == 2 and min(v.shape) >= 64 and v.dtype.is_floating_point:
            mats[k] = v.float()
    return mats

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "--synthetic"
    if arg == "--synthetic":
        torch.manual_seed(20260718)
        g = torch.randn(512, 2048)
        mats = {"gauss": torch.randn(512, 2048), "heavy": g * g.abs() ** 1.5}
    else:
        obj = torch.load(arg, map_location="cpu", weights_only=False)
        sd = obj.get("model", obj.get("state_dict", obj)) if isinstance(obj, dict) else obj.state_dict()
        sd = {k: v for k, v in sd.items()}
        mats = collect_mats(sd)
        print(f"чекпоинт: {arg}, 2D-матриц: {len(mats)}")
    out = {}
    for N in (4, 6, 8, 16):
        rows = []
        for name, kind, kw in fixed_arms(N):
            tot_n, tot_d = 0.0, 0.0
            for W in mats.values():
                q = scaled_qd(W, kind, block=None, **kw)
                tot_n += float((W.double() ** 2).sum()); tot_d += float(((W.double() - q) ** 2).sum())
            rows.append((name, round(10 * __import__("math").log10(tot_n / max(tot_d, 1e-30)), 2)))
        tot_n, tot_d = 0.0, 0.0
        for W in mats.values():
            q = gfplus_a(W, N)
            tot_n += float((W.double() ** 2).sum()); tot_d += float(((W.double() - q) ** 2).sum())
        rows.append((f"GF{N}+A", round(10 * __import__("math").log10(tot_n / max(tot_d, 1e-30)), 2)))
        out[N] = rows
        best = max(r[1] for r in rows)
        print(f"\n=== Класс {N} бит (SQNR дБ, per-row scale, агрегат по всем матрицам) ===")
        for name, s in sorted(rows, key=lambda r: -r[1]):
            print(f"  {name:<16}{s:>8.2f}" + ("  <- best" if s == best else ""))
    json.dump(out, open("gfplus_leaderboard.json", "w"), indent=1)
    print("\nsaved gfplus_leaderboard.json")
