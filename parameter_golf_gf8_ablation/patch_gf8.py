"""Патчер: train_gpt_cuda_ternary.py (Ifrim, официальный рекорд) -> train_gpt_cuda_gf8.py
Добавляет FP_STORAGE=GF8 (per-row scaled GF8 e3m4) и FP_STORAGE=FP8S (per-row scaled e4m3
для честной 2x2 абляции формат x масштабирование).
Каждый анкор проверяется на ЕДИНСТВЕННОСТЬ вхождения — иначе патч падает, не молчит."""
import sys

SRC = "train_gpt_cuda_ternary.py"
DST = "train_gpt_cuda_gf8.py"

text = open(SRC).read()
orig_len = len(text)

def replace_once(old, new, tag):
    global text
    n = text.count(old)
    if n != 1:
        print(f"FAIL [{tag}]: анкор найден {n} раз (нужно ровно 1)"); sys.exit(1)
    text = text.replace(old, new)
    print(f"OK   [{tag}]")

# 1) импорт: каскад FA3 -> FA2 -> SDPA (Blackwell sm_120 не поддержан FA3-Hopper) + gf8
ATTN_FALLBACK = '''
def _pick_attn():
    """FA3 -> FA2 -> torch SDPA; runtime-смоктест ловит несовместимость архитектуры GPU."""
    import os as _os
    import torch as _t
    if _t.cuda.is_available():
        _t.cuda.set_device(int(_os.environ.get("LOCAL_RANK", "0")))
    def _smoke(fn):
        if not _t.cuda.is_available():
            return True
        q = _t.zeros(1, 4, 8, 16, dtype=_t.bfloat16, device="cuda")
        fn(q, q, q, causal=True)
        return True
    try:
        from flash_attn_interface import flash_attn_func as _fa3
        def _f3(q, k, v, causal=True):
            o = _fa3(q, k, v, causal=causal)
            return o[0] if isinstance(o, tuple) else o
        _smoke(_f3)
        return _f3, "fa3"
    except Exception:
        pass
    try:
        from flash_attn import flash_attn_func as _fa2
        _smoke(_fa2)
        return _fa2, "fa2"
    except Exception:
        pass
    import torch.nn.functional as _F
    def _sdpa(q, k, v, causal=True):
        qT, kT, vT = q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2)
        try:
            o = _F.scaled_dot_product_attention(qT, kT, vT, is_causal=causal, enable_gqa=True)
        except TypeError:  # старый torch без enable_gqa
            r = qT.size(1) // kT.size(1)
            o = _F.scaled_dot_product_attention(qT, kT.repeat_interleave(r, 1),
                                                vT.repeat_interleave(r, 1), is_causal=causal)
        return o.transpose(1, 2)
    _smoke(_sdpa)
    return _sdpa, "sdpa"

flash_attn_func, _ATTN_BACKEND = _pick_attn()
print(f"[attn] backend = {_ATTN_BACKEND}", flush=True)
'''

replace_once(
    "from flash_attn_interface import flash_attn_func",
    ATTN_FALLBACK.strip() + "\n"
    "from gf8_quant import gf8_encode, gf8_decode, gf8_qat_ste, gf8_quant_dequant, MAX_NORMAL as GF8_MAX",
    "import")

# 2) парсинг env: GF8 и FP8S
replace_once(
    '    fp_storage = True if _fp_raw == "FP8" else ("fp4" if _fp_raw == "FP4" else False)',
    '    fp_storage = ("gf8" if _fp_raw == "GF8" else\n'
    '                  "fp8s" if _fp_raw == "FP8S" else\n'
    '                  True if _fp_raw == "FP8" else ("fp4" if _fp_raw == "FP4" else False))',
    "env-parse")

# 3) QAT STE: ветки gf8 / fp8s ПЕРЕД веткой fp8 (иначе gf8 truthy провалится в cast e4m3)
replace_once(
    '    elif fp_storage is True or fp_storage == "fp8":\n'
    '        w_sim = w.to(torch.float8_e4m3fn).to(w.dtype)\n'
    '        return (w_sim - w).detach() + w',
    '    elif fp_storage == "gf8":\n'
    '        return gf8_qat_ste(w)\n'
    '    elif fp_storage == "fp8s":  # e4m3 + per-row absmax scale (контроль абляции)\n'
    '        scale = (w.detach().abs().amax(dim=-1, keepdim=True).to(torch.float32) / 448.0).clamp(min=1e-12)\n'
    '        w_sim = ((w.to(torch.float32) / scale).to(torch.float8_e4m3fn).to(torch.float32) * scale).to(w.dtype)\n'
    '        return (w_sim - w).detach() + w\n'
    '    elif fp_storage is True or fp_storage == "fp8":\n'
    '        w_sim = w.to(torch.float8_e4m3fn).to(w.dtype)\n'
    '        return (w_sim - w).detach() + w',
    "qat-ste")

# 4) сериализация: gf8/fp8s ПЕРЕД generic fp8-веткой
replace_once(
    '        elif fp_storage and t.ndim == 2:\n'
    '            quantized[name] = {"type": "fp8", "data": t.to(torch.float8_e4m3fn)}\n'
    '            stats["fp_params"] += t.numel()\n'
    '            stats["fp_bytes"] += t.numel()',
    '        elif fp_storage == "gf8" and t.ndim == 2:\n'
    '            codes, scale = gf8_encode(t.float())\n'
    '            quantized[name] = {"type": "gf8", "codes": codes.cpu(), "scale": scale.cpu(),\n'
    '                               "shape": list(t.shape)}\n'
    '            stats["fp_params"] += t.numel()\n'
    '            stats["fp_bytes"] += codes.numel() + scale.numel() * 2\n'
    '        elif fp_storage == "fp8s" and t.ndim == 2:\n'
    '            sc = (t.float().abs().amax(dim=-1, keepdim=True) / 448.0).clamp(min=1e-12)\n'
    '            quantized[name] = {"type": "fp8s", "data": (t.float() / sc).to(torch.float8_e4m3fn),\n'
    '                               "scale": sc.half()}\n'
    '            stats["fp_params"] += t.numel()\n'
    '            stats["fp_bytes"] += t.numel() + sc.numel() * 2\n'
    '        elif fp_storage and t.ndim == 2:\n'
    '            quantized[name] = {"type": "fp8", "data": t.to(torch.float8_e4m3fn)}\n'
    '            stats["fp_params"] += t.numel()\n'
    '            stats["fp_bytes"] += t.numel()',
    "serialize")

# 5) десериализация
replace_once(
    '        elif entry["type"] == "fp8":\n'
    '            out[name] = entry["data"].to(torch.float32).to(target_dtype).contiguous()',
    '        elif entry["type"] == "gf8":\n'
    '            out[name] = gf8_decode(entry["codes"], entry["scale"], target_dtype).contiguous()\n'
    '        elif entry["type"] == "fp8s":\n'
    '            out[name] = (entry["data"].to(torch.float32) * entry["scale"].to(torch.float32)\n'
    '                         ).to(target_dtype).contiguous()\n'
    '        elif entry["type"] == "fp8":\n'
    '            out[name] = entry["data"].to(torch.float32).to(target_dtype).contiguous()',
    "deserialize")

open(DST, "w").write(text)
print(f"\nЗаписан {DST}: {orig_len} -> {len(text)} байт (+{len(text)-orig_len})")
