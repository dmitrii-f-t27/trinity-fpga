#!/usr/bin/env python3
"""Micro-QAT ablation: does format ordering persist under STE training?

Tests 4 arms: fp32-baseline / fp8+S / gf8+S / e2m5+S
Same 29M model, 3000 steps, 3 seeds. Threshold: 0.005 BPB difference.

Paste in Web Terminal:
  curl -s https://cdn.jsdelivr.net/gh/gHashTag/trinity-fpga@main/webterm_qat.py | python3
"""
import os, sys, json, math
import numpy as np

# Install deps
print("Installing deps...")
os.system("pip3 install --upgrade typing_extensions -q 2>&1 | tail -1")
os.system("pip3 uninstall -y torch torchvision torchaudio 2>/dev/null")
os.system("pip3 install torch --pre --index-url https://download.pytorch.org/whl/nightly/cu128 -q 2>&1 | tail -3")
os.system("pip3 install --upgrade typing_extensions -q 2>&1 | tail -1")
os.system("pip3 install sentencepiece huggingface-hub -q 2>&1 | tail -1")

import torch
import torch.nn as nn, torch.nn.functional as F
import sentencepiece as spm

GPU = torch.cuda.get_device_name(0)
print(f"GPU: {GPU} | PyTorch: {torch.__version__}")

# Setup data
os.chdir("/workspace")
if not os.path.exists("parameter-golf"):
    os.system("git clone --depth 1 https://github.com/openai/parameter-golf.git")
os.chdir("/workspace/parameter-golf")
if not os.path.exists("data/datasets/fineweb10B_sp1024/fineweb_val_000000.bin"):
    os.system("python3 data/cached_challenge_fineweb.py --variant sp1024 --train-shards 1 2>&1 | tail -2")

device = 'cuda'
VOCAB=1024; D=512; NL=9; SEQ=1024; BATCH=48; STEPS=3000

val = np.memmap('data/datasets/fineweb10B_sp1024/fineweb_val_000000.bin', dtype=np.uint16, mode='r')
train_t = torch.tensor(val[:8000000].astype(np.int64))
val_t = torch.tensor(val[8000000:].astype(np.int64))

sp = spm.SentencePieceProcessor(model_file='data/tokenizers/fineweb_1024_bpe.model')
bb = torch.zeros(VOCAB, dtype=torch.int16); hs = torch.zeros(VOCAB, dtype=torch.bool); ib = torch.zeros(VOCAB, dtype=torch.bool)
for t in range(VOCAB):
    d = sp.decode([t])
    if d: bb[t] = len(d.encode('utf-8')); hs[t] = d[0]==' '
    if sp.is_unknown(t) or sp.is_control(t) or sp.is_byte(t): ib[t]=True; bb[t]=0

class Model(nn.Module):
    def __init__(s):
        super().__init__()
        s.e=nn.Embedding(VOCAB,D);s.p=nn.Embedding(SEQ,D)
        s.l=nn.ModuleList([nn.TransformerEncoderLayer(d_model=D,nhead=8,dim_feedforward=D*4,dropout=0.1,batch_first=True,activation='gelu',norm_first=True) for _ in range(NL)])
        s.f=nn.LayerNorm(D);s.h=nn.Linear(D,VOCAB,bias=False);s.h.weight=s.e.weight
    def forward(s,x):
        h=s.e(x)+s.p(torch.arange(x.size(1),device=x.device))
        for b in s.l:h=b(h)
        return s.h(s.f(h))

# ═══ QAT quantizers with STE (straight-through estimator) ═══

def ste_qat_fp8_scaled():
    """FP8 E4M3 with per-row scaling + STE"""
    MX = 448.0
    def f(w):
        if w.dim() < 2: return w
        scale = (w.detach().abs().amax(dim=-1,keepdim=True)/MX).clamp(min=1e-12)
        w_sim = (w/scale).to(torch.float8_e4m3fn).to(w.dtype) * scale
        return (w_sim - w).detach() + w  # STE
    return f

def ste_qat_gf8_scaled():
    """GF8 E3M4 (φ-rule) with per-row scaling + STE"""
    E,BIAS,Mm = 3,3,4
    MX = (2.0**((1<<E)-1-BIAS))*(2.0-2.0**(-Mm))  # 31.0
    B = (1<<(E-1))-1; EM = (1<<E)-1; MV = 2.0**(1-B-Mm); ms = float(1<<Mm)
    def f(w):
        if w.dim() < 2: return w
        scale = (w.detach().abs().amax(dim=-1,keepdim=True)/MX).clamp(min=1e-12)
        ws = w / scale
        sg = torch.sign(ws); a = torch.abs(ws).clamp(min=MV)
        e = torch.floor(torch.log2(a)); ff = a/(2.0**e); ef = torch.clamp(e+B,1,EM-1)
        w_sim = sg*(1+torch.round((ff-1)*ms)/ms)*(2.0**(ef-B))
        w_sim = torch.where(torch.abs(ws)<MV, torch.zeros_like(w_sim), w_sim)
        w_sim = torch.clamp(w_sim, -MX, MX) * scale
        return (w_sim - w).detach() + w  # STE
    return f

def ste_qat_e2m5_scaled():
    """E2M5 (narrow-exponent) with per-row scaling + STE"""
    E,BIAS,Mm = 2,1,5
    MX = (2.0**((1<<E)-1-BIAS))*(2.0-2.0**(-Mm))  # 3.96875
    B = (1<<(E-1))-1; EM = (1<<E)-1; MV = 2.0**(1-B-Mm); ms = float(1<<Mm)
    def f(w):
        if w.dim() < 2: return w
        scale = (w.detach().abs().amax(dim=-1,keepdim=True)/MX).clamp(min=1e-12)
        ws = w / scale
        sg = torch.sign(ws); a = torch.abs(ws).clamp(min=MV)
        e = torch.floor(torch.log2(a)); ff = a/(2.0**e); ef = torch.clamp(e+B,1,EM-1)
        w_sim = sg*(1+torch.round((ff-1)*ms)/ms)*(2.0**(ef-B))
        w_sim = torch.where(torch.abs(ws)<MV, torch.zeros_like(w_sim), w_sim)
        w_sim = torch.clamp(w_sim, -MX, MX) * scale
        return (w_sim - w).detach() + w  # STE
    return f

def eval_bpb(m):
    m.eval()
    ls=0.;tk=0;by=0
    bl=bb.to(device);hp=hs.to(device);ip=ib.to(device)
    with torch.no_grad():
        for i in range(0,len(val_t)-SEQ-1,SEQ*4):
            x=val_t[i:i+SEQ].unsqueeze(0).to(device);y=val_t[i+1:i+SEQ+1].unsqueeze(0).to(device)
            if x.size(1)<SEQ:continue
            lg=m(x).reshape(-1,VOCAB);yt=y.reshape(-1)
            ls+=F.cross_entropy(lg,yt,reduction='sum').item();tk+=SEQ
            pv=x.reshape(-1);tb=bl[yt].sum().item();tb+=(hp[yt]&~ip[pv]).int().sum().item();by+=max(tb,1)
    m.train()
    return ls/tk/math.log(2)*tk/by

# ═══ Run QAT ablation: 4 arms × 3 seeds ═══
SEEDS = [42, 123, 777]
ARMS = {
    "FP32 (no QAT)": None,
    "FP8+S E4M3": ste_qat_fp8_scaled(),
    "GF8+S E3M4": ste_qat_gf8_scaled(),
    "E2M5+S": ste_qat_e2m5_scaled(),
}

print(f"\n{'='*70}")
print(f"MICRO-QAT ABLATION — {GPU}")
print(f"Model:{NL}L d={D} seq={SEQ}|{sum(p.numel() for p in Model().parameters()):,}params|{STEPS}steps")
print(f"Arms: {list(ARMS.keys())}")
print(f"Seeds: {SEEDS}")
print(f"{'='*70}\n")

all_results = {}

for arm_name, qat_fn in ARMS.items():
    print(f"--- ARM: {arm_name} ---")
    bpbs = []
    for seed in SEEDS:
        torch.manual_seed(seed)
        model = Model().to(device)
        opt = torch.optim.AdamW(model.parameters(), lr=0.003, weight_decay=0.1, betas=(0.95,0.95))

        for step in range(STEPS+1):
            idx = torch.randint(0, len(train_t)-SEQ-1, (BATCH,))
            x = torch.stack([train_t[i:i+SEQ] for i in idx]).to(device)
            y = torch.stack([train_t[i+1:i+SEQ+1] for i in idx]).to(device)

            # Apply QAT fake quantization BEFORE forward pass
            if qat_fn is not None:
                saved = {}
                for n, p in model.named_parameters():
                    if p.dim() >= 2:
                        saved[n] = p.data.clone()
                        p.data = qat_fn(p.data)

            loss = F.cross_entropy(model(x).reshape(-1, VOCAB), y.reshape(-1))
            opt.zero_grad(); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)

            # Restore original weights for optimizer update
            if qat_fn is not None:
                for n, p in model.named_parameters():
                    if n in saved:
                        p.data = saved[n]

            opt.step()

            if step % 1000 == 0:
                print(f"  seed={seed} step={step}/{STEPS} loss={loss.item():.4f}", flush=True)

        bpb = eval_bpb(model)
        bpbs.append(bpb)
        print(f"  seed={seed} FINAL BPB={bpb:.4f}")

    mean_bpb = sum(bpbs)/len(bpbs)
    std_bpb = (sum((b-mean_bpb)**2 for b in bpbs)/len(bpbs))**0.5
    all_results[arm_name] = {"mean": mean_bpb, "std": std_bpb, "seeds": bpbs}
    print(f"  MEAN BPB={mean_bpb:.4f} ± {std_bpb:.4f}\n")

# ═══ Summary ═══
print(f"\n{'='*70}")
print(f"QAT ABLATION RESULTS — {GPU}")
print(f"{'='*70}")
print(f"\n{'Arm':<18}{'Mean BPB':>10}{'± Std':>10}{'Seeds':>30}")
print("-"*70)
for arm, data in all_results.items():
    seeds_str = str([f"{s:.4f}" for s in data["seeds"]])
    print(f"{arm:<18}{data['mean']:>10.4f}{data['std']:>10.4f}  {seeds_str}")

# Compare
fp32_mean = all_results["FP32 (no QAT)"]["mean"]
print(f"\n{'Arm':<18}{'Δ vs FP32':>10}{'Significant?':>15}")
print("-"*45)
for arm, data in all_results.items():
    delta = data["mean"] - fp32_mean
    sig = "YES" if abs(delta) > 0.005 else "no (noise)"
    print(f"{arm:<18}{delta:>+10.4f}  {sig:>12}")

json.dump(all_results, open('/workspace/qat_results.json', 'w'), indent=2)
print(f"\nSaved: /workspace/qat_results.json")
print("DONE")
