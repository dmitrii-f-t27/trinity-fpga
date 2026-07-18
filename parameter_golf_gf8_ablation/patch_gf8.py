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

# 1) импорт модуля
replace_once(
    "from flash_attn_interface import flash_attn_func",
    "from flash_attn_interface import flash_attn_func\n"
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
