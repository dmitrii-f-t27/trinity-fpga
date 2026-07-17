"""
SQ-INT6 Integration Patch for Parameter Golf train_gpt.py

Apply this patch to add SmoothQuant INT6 as an alternative quantization format.
The patch is non-invasive: it only activates when QUANT_FORMAT=sq_int6 env var is set.

Usage:
  # Apply manually: add these functions to train_gpt.py
  
  # Then use:
  QUANT_FORMAT=sq_int6 python3 train_gpt.py
  
  # Or compare:
  python3 train_gpt.py                          # baseline INT8
  QUANT_FORMAT=sq_int6 python3 train_gpt.py     # our SQ-INT6
"""

# PASTE these functions into train_gpt.py (after the existing quantize_state_dict_int8):

def smoothquant_weight(W, alpha=0.5):
    """SmoothQuant: redistribute outlier magnitude between rows and columns."""
    col_max = W.abs().amax(dim=0, keepdim=True).clamp(min=1e-8)
    row_max = W.abs().amax(dim=1, keepdim=True).clamp(min=1e-8)
    scale = (col_max.pow(alpha) * row_max.pow(1 - alpha)).clamp(min=1e-8)
    return W / scale, col_max.squeeze(0), row_max.squeeze(1)


def quantize_state_dict_sq_int6(state_dict):
    """SmoothQuant + INT6 quantization. Drop-in for quantize_state_dict_int8."""
    SQ_ALPHA = float(os.environ.get("SQ_ALPHA", "0.5"))
    INT_BITS = 6
    LEVELS = (1 << (INT_BITS - 1)) - 1  # 31
    KEEP_MAX = 65_536
    
    quantized = {}
    passthrough = {}
    
    for name, tensor in state_dict.items():
        t = tensor.detach().cpu().contiguous()
        
        if not t.is_floating_point() or t.numel() <= KEEP_MAX:
            # Keep small/non-float tensors as-is (FP16 for floats)
            passthrough[name] = t.to(torch.float16).contiguous() if t.is_floating_point() else t
            continue
        
        t32 = t.float()
        
        # Apply SmoothQuant
        smoothed, col_s, row_s = smoothquant_weight(t32, SQ_ALPHA)
        
        # Per-row INT6 quantization
        row_max = smoothed.abs().amax(dim=1, keepdim=True).clamp(min=1e-8)
        int_scale = row_max / LEVELS
        q = torch.clamp(torch.round(smoothed / int_scale), -32, 31).to(torch.int8)
        
        quantized[name] = {
            "q": q.contiguous(),
            "int_scale": int_scale.squeeze(1).to(torch.float16).contiguous(),
            "col_scale": col_s.to(torch.float16).contiguous(),
            "row_scale": row_s.to(torch.float16).contiguous(),
        }
    
    return {"__format__": "sq_int6", "quantized": quantized, "passthrough": passthrough}, {}


def dequantize_state_dict_sq_int6(obj):
    """Dequantize SQ-INT6 back to FP32."""
    SQ_ALPHA = float(os.environ.get("SQ_ALPHA", "0.5"))
    result = {}
    
    for name, data in obj["quantized"].items():
        q = data["q"].float()
        int_s = data["int_scale"].float().unsqueeze(1)
        col_s = data["col_scale"].float().unsqueeze(0)
        row_s = data["row_scale"].float().unsqueeze(1)
        
        smoothed = q * int_s
        scale = col_s.pow(SQ_ALPHA) * row_s.pow(1 - SQ_ALPHA)
        result[name] = (smoothed * scale).contiguous()
    
    for name, t in obj["passthrough"].items():
        result[name] = t.float() if t.is_floating_point() else t
    
    return result


# ═══ INTEGRATION POINT in train_gpt.py (line ~1076) ═══
# REPLACE:
#   quant_obj, quant_stats = quantize_state_dict_int8(base_model.state_dict())
# WITH:
import os
if os.environ.get("QUANT_FORMAT") == "sq_int6":
    quant_obj, quant_stats = quantize_state_dict_sq_int6(base_model.state_dict())
else:
    quant_obj, quant_stats = quantize_state_dict_int8(base_model.state_dict())

# ═══ DEQUANTIZATION POINT (line ~1099) ═══
# REPLACE:
#   base_model.load_state_dict(dequantize_state_dict_int8(quant_state), strict=True)
# WITH:
if quant_state.get("__format__") == "sq_int6":
    base_model.load_state_dict(dequantize_state_dict_sq_int6(quant_state), strict=True)
else:
    base_model.load_state_dict(dequantize_state_dict_int8(quant_state), strict=True)
