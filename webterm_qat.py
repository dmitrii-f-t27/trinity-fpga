#!/usr/bin/env python3
"""Micro-QAT: sequential arms, save after each, resumable"""
import os, sys, json, math
import numpy as np

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

os.chdir("/workspace")
if not os.path.exists("parameter-golf"):
    os.system("git clone --depth 1 https://github.com/openai/parameter-golf.git")
os.chdir("/workspace/parameter-golf")
if not os.path.exists("data/datasets/fineweb10B_sp1024/fineweb_val_000000.bin"):
    os.system("python3 data/cached_challenge_fineweb.py --variant sp1024 --train-shards 1 2>&1 | tail -2")

device='cuda'; VOCAB=1024; D=512; NL=9; SEQ=1024; BATCH=48; STEPS=2000

val=np.memmap('data/datasets/fineweb10B_sp1024/fineweb_val_000000.bin',dtype=np.uint16,mode='r')
train_t=torch.tensor(val[:8000000].astype(np.int64))
val_t=torch.tensor(val[8000000:].astype(np.int64))

sp=spm.SentencePieceProcessor(model_file='data/tokenizers/fineweb_1024_bpe.model')
bb=torch.zeros(VOCAB,dtype=torch.int16);hs=torch.zeros(VOCAB,dtype=torch.bool);ib=torch.zeros(VOCAB,dtype=torch.bool)
for t in range(VOCAB):
    d=sp.decode([t])
    if d: bb[t]=len(d.encode('utf-8'));hs[t]=d[0]==' '
    if sp.is_unknown(t)or sp.is_control(t)or sp.is_byte(t): ib[t]=True;bb[t]=0

class Model(nn.Module):
    def __init__(s):
        super().__init__()
        s.e=nn.Embedding(VOCAB,D);s.p=nn.Embedding(SEQ,D)
        s.l=nn.ModuleList([nn.TransformerEncoderLayer(d_model=D,nhead=8,dim_feedforward=D*4,dropout=0.1,batch_first=True,activation='gelu',norm_first=True)for _ in range(NL)])
        s.f=nn.LayerNorm(D);s.h=nn.Linear(D,VOCAB,bias=False);s.h.weight=s.e.weight
    def forward(s,x):
        h=s.e(x)+s.p(torch.arange(x.size(1),device=x.device))
        for b in s.l:h=b(h)
        return s.h(s.f(h))

def ste_fp8s():
    MX=448.0
    def f(w):
        if w.dim()<2:return w
        sc=(w.detach().abs().amax(dim=-1,keepdim=True)/MX).clamp(min=1e-12)
        sim=(w/sc).to(torch.float8_e4m3fn).to(w.dtype)*sc
        return (sim-w).detach()+w
    return f

def ste_gf8s():
    E,BIAS,Mm=3,3,4;MX=31.0;B=3;EM=7;MV=2.0**(1-3-4);ms=16.0
    def f(w):
        if w.dim()<2:return w
        sc=(w.detach().abs().amax(dim=-1,keepdim=True)/MX).clamp(min=1e-12)
        ws=w/sc;sg=torch.sign(ws);a=torch.abs(ws).clamp(min=MV)
        e=torch.floor(torch.log2(a));ff=a/(2.**e);ef=torch.clamp(e+B,1,EM-1)
        sim=sg*(1+torch.round((ff-1)*ms)/ms)*(2.**(ef-B))
        sim=torch.where(torch.abs(ws)<MV,torch.zeros_like(sim),sim)
        sim=torch.clamp(sim,-MX,MX)*sc
        return (sim-w).detach()+w
    return f

def ste_e2m5s():
    E,BIAS,Mm=2,1,5;MX=(2.0**((1<<E)-1-BIAS))*(2.0-2.0**(-Mm));B=1;EM=3;MV=2.0**(1-1-5);ms=32.0
    def f(w):
        if w.dim()<2:return w
        sc=(w.detach().abs().amax(dim=-1,keepdim=True)/MX).clamp(min=1e-12)
        ws=w/sc;sg=torch.sign(ws);a=torch.abs(ws).clamp(min=MV)
        e=torch.floor(torch.log2(a));ff=a/(2.**e);ef=torch.clamp(e+B,1,EM-1)
        sim=sg*(1+torch.round((ff-1)*ms)/ms)*(2.**(ef-B))
        sim=torch.where(torch.abs(ws)<MV,torch.zeros_like(sim),sim)
        sim=torch.clamp(sim,-MX,MX)*sc
        return (sim-w).detach()+w
    return f

def eval_bpb(m):
    m.eval();ls=0.;tk=0;by=0
    bl=bb.to(device);hp=hs.to(device);ip=ib.to(device)
    with torch.no_grad():
        for i in range(0,len(val_t)-SEQ-1,SEQ*4):
            x=val_t[i:i+SEQ].unsqueeze(0).to(device);y=val_t[i+1:i+SEQ+1].unsqueeze(0).to(device)
            if x.size(1)<SEQ:continue
            lg=m(x).reshape(-1,VOCAB);yt=y.reshape(-1)
            ls+=F.cross_entropy(lg,yt,reduction='sum').item();tk+=SEQ
            pv=x.reshape(-1);tb=bl[yt].sum().item();tb+=(hp[yt]&~ip[pv]).int().sum().item();by+=max(tb,1)
    m.train();return ls/tk/math.log(2)*tk/by

def run_arm(arm_name, qat_fn, seed):
    """Run ONE arm+seed, return BPB."""
    torch.manual_seed(seed)
    model=Model().to(device)
    opt=torch.optim.AdamW(model.parameters(),lr=0.003,weight_decay=0.1,betas=(0.95,0.95))
    for step in range(STEPS+1):
        idx=torch.randint(0,len(train_t)-SEQ-1,(BATCH,))
        x=torch.stack([train_t[i:i+SEQ]for i in idx]).to(device)
        y=torch.stack([train_t[i+1:i+SEQ+1]for i in idx]).to(device)
        if qat_fn:
            saved={n:p.data.clone()for n,p in model.named_parameters()if p.dim()>=2}
            for n,p in model.named_parameters():
                if p.dim()>=2:p.data=qat_fn(p.data)
        loss=F.cross_entropy(model(x).reshape(-1,VOCAB),y.reshape(-1))
        opt.zero_grad();loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
        if qat_fn:
            for n,p in model.named_parameters():
                if n in saved:p.data=saved[n]
        opt.step()
        if step%500==0:
            print(f"    step={step}/{STEPS} loss={loss.item():.3f}",flush=True)
    bpb=eval_bpb(model)
    return bpb

# ═══ SEQUENTIAL: one arm at a time, save after each ═══
ARMS=[("FP32",None),("FP8S",ste_fp8s()),("GF8S",ste_gf8s()),("E2M5S",ste_e2m5s())]
SEED=42  # start with 1 seed, add more if results ambiguous

results={}
for arm_name,qat_fn in ARMS:
    print(f"\n{'='*50}")
    print(f"ARM: {arm_name} (seed={SEED})")
    print(f"{'='*50}")
    bpb=run_arm(arm_name,qat_fn,SEED)
    results[arm_name]=bpb
    print(f"  → BPB={bpb:.4f}")
    # Save after each arm (resumable)
    json.dump(results,open('/workspace/qat_partial.json','w'),indent=2)
    print(f"  Saved to qat_partial.json")
    # Free GPU memory
    torch.cuda.empty_cache()

# Summary
print(f"\n{'='*50}")
print(f"QAT ABLATION RESULTS (seed={SEED}, {STEPS} steps)")
print(f"{'='*50}")
fp32=results.get("FP32",0)
print(f"\n{'Arm':<10}{'BPB':>8}{'Δ':>8}")
print("-"*30)
for arm,bpb in results.items():
    print(f"{arm:<10}{bpb:>8.4f}{bpb-fp32:>+8.4f}")
print("\nDONE")
