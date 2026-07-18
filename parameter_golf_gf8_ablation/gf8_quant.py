"""GF8 (GoldenFloat-8, e3m4) quantization for Parameter Golf ablation.

Поля по φ-правилу GoldenFloat: N=8 -> e = round((N-1)/φ²) = round(7/2.618) = 3,
m = N-1-e = 4, bias = 2^(e-1)-1 = 3.  [источник: правило полей GF, arXiv:2606.05017]

Дизайн кодировки: fn-стиль (как float8_e4m3fn) — БЕЗ inf/nan, все 256 кодов конечны,
насыщение на max normal = 2^4 * (1 + 15/16) = 31.0.
Денормалы: biased_exp=0 -> val = mant * 2^(1-bias-m) = mant * 2^-6.

ВАЖНОЕ ОТЛИЧИЕ ОТ e4m3 (честно): у e3m4 динамический диапазон уже
(min denormal 2^-6 = 0.0156 против 2^-9 у e4m3), но мантисса на 1 бит точнее.
Поэтому GF8-ветка использует per-row absmax-масштабирование (map max -> 31.0),
тогда как fp8-ветка Ifrim — прямой cast без масштаба. Это ЧАСТЬ различия форматов —
фиксируем как дизайн абляции, оверхед скейлов = out_features * 2 байта (fp16).

torch.round = round-half-to-even (RNE).
"""
import torch
from torch import Tensor

E, M, BIAS = 3, 4, 3
EMAX = (1 << E) - 1 - BIAS           # 4  (fn-стиль: старшая биср. экспонента = нормальная)
EMIN = 1 - BIAS                      # -2 (минимальная нормальная экспонента)
MAX_NORMAL = (2.0 ** EMAX) * (2.0 - 2.0 ** (-M))   # 31.0
DENORM_STEP = 2.0 ** (EMIN - M)      # 2^-6


def gf8_quant_dequant(w: Tensor) -> Tensor:
    """Поэлементный quantize->dequantize в GF8 e3m4 (без масштабирования). RNE, денормалы, насыщение."""
    orig_dtype = w.dtype
    a = w.abs().to(torch.float32)
    sign = torch.sign(w.to(torch.float32))
    # нормальный диапазон
    safe = torch.clamp(a, min=1e-45)
    Ee = torch.clamp(torch.floor(torch.log2(safe)), EMIN, EMAX)
    step = torch.exp2(Ee - M)
    q_norm = torch.round(a / step) * step             # RNE
    # денормалы: a < 2^EMIN
    q_den = torch.round(a / DENORM_STEP) * DENORM_STEP
    q = torch.where(a < 2.0 ** EMIN, q_den, q_norm)
    q = torch.clamp(q, max=MAX_NORMAL)                # насыщение (fn)
    q = torch.where(a == 0, torch.zeros_like(q), q)
    return (sign * q).to(orig_dtype)


def gf8_encode(t: Tensor):
    """2D weight -> (codes uint8 [rows, cols], scale fp16 [rows, 1]).
    Per-row absmax scaling: max|row| -> MAX_NORMAL."""
    assert t.ndim == 2, "gf8_encode ожидает 2D"
    w = t.to(torch.float32)
    scale = (w.abs().amax(dim=-1, keepdim=True) / MAX_NORMAL).clamp(min=1e-12)
    ws = w / scale
    sign_bit = (ws < 0).to(torch.uint8)
    a = ws.abs()
    safe = torch.clamp(a, min=1e-45)
    Ee = torch.clamp(torch.floor(torch.log2(safe)), EMIN, EMAX)
    frac = a / torch.exp2(Ee)                          # [1,2) для нормальных
    mant = torch.round((frac - 1.0) * (1 << M))        # RNE
    carry = mant >= (1 << M)
    Ee = Ee + carry.to(Ee.dtype)
    mant = torch.where(carry, torch.zeros_like(mant), mant)
    # переполнение после carry -> насыщение в max код
    ovf = Ee > EMAX
    Ee = torch.clamp(Ee, max=EMAX)
    mant = torch.where(ovf, torch.full_like(mant, (1 << M) - 1), mant)
    biased = (Ee + BIAS).to(torch.uint8)
    # денормалы
    den = a < 2.0 ** EMIN
    mant_d = torch.round(a / DENORM_STEP)
    promote = mant_d >= (1 << M)                       # округлилось вверх до нормали
    mant = torch.where(den & ~promote, mant_d, mant)
    biased = torch.where(den & ~promote, torch.zeros_like(biased), biased)
    biased = torch.where(den & promote, torch.ones_like(biased), biased)
    mant = torch.where(den & promote, torch.zeros_like(mant), mant)
    zero = a == 0
    biased = torch.where(zero, torch.zeros_like(biased), biased)
    mant = torch.where(zero, torch.zeros_like(mant), mant)
    codes = (sign_bit << (E + M)) | (biased << M) | mant.to(torch.uint8)
    return codes.contiguous(), scale.half()


def gf8_decode(codes: Tensor, scale: Tensor, target_dtype=torch.bfloat16) -> Tensor:
    """(codes uint8, scale fp16) -> веса."""
    c = codes.to(torch.int32)
    sign = 1.0 - 2.0 * ((c >> (E + M)) & 1).to(torch.float32)
    be = ((c >> M) & ((1 << E) - 1)).to(torch.float32)
    mant = (c & ((1 << M) - 1)).to(torch.float32)
    normal = torch.exp2(be - BIAS) * (1.0 + mant / (1 << M))
    denorm = mant * DENORM_STEP
    val = torch.where(be == 0, denorm, normal) * sign
    return (val * scale.to(torch.float32)).to(target_dtype)


def gf8_qat_ste(w: Tensor) -> Tensor:
    """STE: forward через GF8 (per-row scaled), grad мимо. Формат-симуляция для QAT."""
    scale = (w.detach().abs().amax(dim=-1, keepdim=True).to(torch.float32) / MAX_NORMAL).clamp(min=1e-12)
    w_sim = (gf8_quant_dequant(w.to(torch.float32) / scale) * scale).to(w.dtype)
    return (w_sim - w).detach() + w


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    torch.manual_seed(20260718)
    # 1) exhaustive: все 256 кодов декодируются и реэнкодируются канонично
    codes = torch.arange(256, dtype=torch.uint8).reshape(1, -1)
    ones = torch.ones(1, 1)
    vals = gf8_decode(codes, ones, torch.float32)
    # идемпотентность quant_dequant на решётке формата
    qd = gf8_quant_dequant(vals)
    idem = torch.equal(qd, vals)
    # реэнкод (масштаб подобран так, что absmax=31 -> scale=1)
    v2 = vals.clone(); v2[0, -1] = MAX_NORMAL  # гарантируем absmax=31
    c2, s2 = gf8_encode(v2)
    v3 = gf8_decode(c2, s2, torch.float32)
    roundtrip = torch.allclose(v3, v2, atol=0, rtol=0)
    # 2) насыщение и нули
    t = torch.tensor([[0.0, 1e-9, 100.0, -100.0, 0.015625, 31.0]])
    c, s = gf8_encode(t)
    back = gf8_decode(c, s, torch.float32)
    # 3) STE-градиент проходит
    w = torch.randn(4, 16, requires_grad=True)
    y = gf8_qat_ste(w).sum(); y.backward()
    grad_ok = torch.allclose(w.grad, torch.ones_like(w))
    # 4) ошибка представления на гауссе (сравнить с e4m3 прямым cast)
    g = torch.randn(1000, 1000)
    sc = g.abs().amax(dim=-1, keepdim=True) / MAX_NORMAL
    gf8_err = (gf8_quant_dequant(g / sc) * sc - g).pow(2).mean().sqrt()
    try:
        e4m3_err = (g.to(torch.float8_e4m3fn).to(torch.float32) - g).pow(2).mean().sqrt()
    except Exception:
        e4m3_err = float("nan")
    print(f"idempotent(256 codes): {idem}")
    print(f"roundtrip encode/decode: {roundtrip}")
    print(f"corner cases: in={t.tolist()} out={back.tolist()}")
    print(f"STE grad pass-through: {grad_ok}")
    print(f"RMSE gauss: gf8_scaled={gf8_err:.6f} e4m3_direct={e4m3_err:.6f}")
    assert idem and roundtrip and grad_ok
    print("ALL CHECKS PASSED")
