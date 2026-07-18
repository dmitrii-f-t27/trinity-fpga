#!/usr/bin/env python3
"""Paste this entire file into RunPod Web Terminal: python3 <paste>"""
import subprocess, sys, os, time

# Step 1: Install PyTorch nightly for Blackwell
print("=== Installing PyTorch cu128 ===")
subprocess.run([sys.executable, "-m", "pip", "install", "--pre", "torch", 
    "--index-url", "https://download.pytorch.org/whl/nightly/cu128",
    "--no-deps", "-q"], check=False)
subprocess.run([sys.executable, "-m", "pip", "install", 
    "sentencepiece", "huggingface-hub", "-q"], check=False)

# Step 2: Clone repo + download data
os.chdir("/workspace")
if not os.path.exists("parameter-golf"):
    subprocess.run(["git", "clone", "--depth", "1", 
        "https://github.com/openai/parameter-golf.git"], check=True)

os.chdir("/workspace/parameter-golf")
if not os.path.exists("data/datasets/fineweb10B_sp1024/fineweb_val_000000.bin"):
    subprocess.run([sys.executable, "data/cached_challenge_fineweb.py",
        "--variant", "sp1024", "--train-shards", "1"], check=True)

# Step 3: Run training + format comparison
import torch, torch.nn as nn, torch.nn.functional as F
import numpy as np, math, json
import sentencepiece as spm

device = 'cuda'
VOCAB=1024; D=512; NL=9; SEQ=1024; BATCH=48; STEPS=3000

val = np.memmap('/workspace/parameter-golf/data/datasets/fineweb10B_sp1024/fineweb_val_000000.bin', dtype=np.uint16, mode='r')
train = torch.tensor(val[:8000000].astype(np.int64))
val_t = torch.tensor(val[8000000:].astype(np.int64))

sp = spm.SentencePieceProcessor(model_file='/workspace/parameter-golf/data/tokenizers/fineweb_1024_bpe.model')
base_bytes = torch.zeros(VOCAB, dtype=torch.int16)
has_space = torch.zeros(VOCAB, dtype=torch.bool)
is_bnd = torch.zeros(VOCAB, dtype=torch.bool)
for t in range(VOCAB):
    d = sp.decode([t])
    if d:
        base_bytes[t] = len(d.encode('utf-8'))
        if d[0] == ' ': has_space[t] = True
    if sp.is_unknown(t) or sp.is_control(t) or sp.is_byte(t):
        is_bnd[t] = True; base_bytes[t] = 0

print(f"Data: {len(train)} train, {len(val_t)} val, avg bytes/tok: {base_bytes.float().mean():.2f}")

class M(nn.Module):
    def __init__(s):
        super().__init__()
        s.e=nn.Embedding(VOCAB,D); s.p=nn.Embedding(SEQ,D)
        s.l=nn.ModuleList([nn.TransformerEncoderLayer(
            d_model=D,nhead=8,dim_feedforward=D*4,dropout=0.1,
            batch_first=True,activation='gelu',norm_first=True) for _ in range(NL)])
        s.f=nn.LayerNorm(D); s.h=nn.Linear(D,VOCAB,bias=False); s.h.weight=s.e.weight
    def forward(s,x):
        h=s.e(x)+s.p(torch.arange(x.size(1),device=x.device))
        for b in s.l: h=b(h)
        return s.h(s.f(h))

def qg(E,Mm):
    B=(1<<(E-1))-1;EM=(1<<E)-1;MV=2.**(1-B-Mm);ms=float(1<<Mm)
    def f(t):
        sg=torch.sign(t);a=torch.abs(t).clamp(min=MV);e=torch.floor(torch.log2(a));ff=a/(2.**e);ef=torch.clamp(e+B,1,EM-1)
        r=sg*(1+torch.round((ff-1)*ms)/ms)*(2.**(ef-B));return torch.where(torch.abs(t)<MV,torch.zeros_like(r),r)
    return f

def qi(b):
    lv=(1<<(b-1))-1
    def f(t):
        mx=t.abs().max();return torch.round(t/(mx/lv)).clamp(-lv-1,lv)*(mx/lv) if mx>0 else t
    return f

def qs(b,a=0.5):
    lv=(1<<(b-1))-1
    def f(t):
        if t.dim()<2:return qi(b)(t)
        cm=t.abs().amax(dim=0,keepdim=True).clamp(min=1e-8);rm=t.abs().amax(dim=1,keepdim=True).clamp(min=1e-8)
        sc=(cm.pow(a)*rm.pow(1-a)).clamp(min=1e-8);sm=t/sc;mx=sm.abs().max()
        return torch.round(sm/(mx/lv)).clamp(-lv-1,lv)*(mx/lv)*sc if mx>0 else t
    return f

def ev(m,qf=None):
    m.eval()
    if qf:
        o={n:p.data.clone()for n,p in m.named_parameters()if p.dim()>=2}
        for n,p in m.named_parameters():
            if p.dim()>=2:p.data=qf(p.data)
    ls=0.;tk=0;by=0
    bl=base_bytes.to(device);hs=has_space.to(device);ib=is_bnd.to(device)
    with torch.no_grad():
        for i in range(0,len(val_t)-SEQ-1,SEQ*4):
            x=val_t[i:i+SEQ].unsqueeze(0).to(device);y=val_t[i+1:i+SEQ+1].unsqueeze(0).to(device)
            if x.size(1)<SEQ:continue
            lg=m(x).reshape(-1,VOCAB);yt=y.reshape(-1)
            ls+=F.cross_entropy(lg,yt,reduction='sum').item();tk+=SEQ
            pv=x.reshape(-1);tb=bl[yt].sum().item();tb+=(hs[yt]&~ib[pv]).int().sum().item();by+=max(tb,1)
    if qf:
        for n,p in m.named_parameters():
            if n in o:p.data=o[n]
    m.train()
    return ls/tk/math.log(2)*tk/by

print(f"\nTraining {NL}L d={D} {STEPS} steps on {torch.cuda.get_device_name(0)}...")
torch.manual_seed(42);model=M().to(device)
# Muon-like optimizer: higher LR for matrix params
op=torch.optim.AdamW(model.parameters(),lr=0.003,weight_decay=0.1,betas=(0.95,0.95))
for s in range(STEPS+1):
    idx=torch.randint(0,len(train)-SEQ-1,(BATCH,))
    x=torch.stack([train[i:i+SEQ]for i in idx]).to(device)
    y=torch.stack([train[i+1:i+SEQ+1]for i in idx]).to(device)
    loss=F.cross_entropy(model(x).reshape(-1,VOCAB),y.reshape(-1))
    op.zero_grad();loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);op.step()
    if s%500==0:
        bpb=ev(model);print(f"  {s}/{STEPS}: loss={loss.item():.4f} bpb={bpb:.4f}",flush=True)

b=ev(model)
P=sum(p.numel()for p in model.parameters())
print(f"\n{'='*65}")
print(f"FORMAT LEADERBOARD — {torch.cuda.get_device_name(0)}")
print(f"Model:{NL}L d={D} seq={SEQ}|{P:,}params|{STEPS}steps|FineWeb sp1024")
print(f"{'='*65}")
print(f"\n{'Format':<12}{'Family':<7}{'bpe':>4}{'BPB':>9}{'Delta':>9}{'Status'}")
print("-"*55)
print(f"{'FP32':<12}{'FP':<7}{32:>4}{b:>9.4f}{'—':>9}master")
R={'FP32':b}
for nm,qf,w,fam in[
    ('FP16',qg(5,10),16,'FP'),('BF16',qg(8,7),16,'FP'),
    ('GF14+',qg(5,8),14,'GF'),('GF16+',qg(6,9),16,'GF'),('GF20',qg(7,12),20,'GF'),
    ('GF24',qg(9,14),24,'GF'),
    ('INT8',qi(8),8,'INT'),('INT7',qi(7),7,'INT'),('INT6',qi(6),6,'INT'),
    ('SQ-INT7',qs(7),7,'SQ'),('SQ-INT6',qs(6),6,'SQ'),
]:
    r=ev(model,qf);dl=r-b;R[nm]=r
    st='lossless'if abs(dl)<0.001 else('good'if abs(dl)<0.01 else'noisy')
    star='★'if'SQ'in nm else''
    print(f'{nm:<12}{fam:<7}{w:>4}{r:>9.4f}{dl:>+9.4f} {st} {star}')
json.dump(R,open('/workspace/leaderboard.json','w'),indent=2)
print(f"\nSaved: /workspace/leaderboard.json")
print("DONE")
