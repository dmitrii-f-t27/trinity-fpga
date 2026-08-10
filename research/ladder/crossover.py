"""Can the crossover be predicted from the weight distribution alone?

Measured MSE ranks the ladders correctly (T31), but measuring it still needs a
pass over every weight for every candidate. If the MSE has a closed form in the
distribution, the rung follows from a histogram and a budget -- which is a law
rather than a procedure.

Model. Normalise each channel by its maximum, so levels are r^-k for
k = 0..n-1 with n = (2^b - 1)/2 magnitudes.

  * In range, a geometric ladder rounds with bounded RELATIVE error. Rounding
    x to the nearer of r^-k, r^-(k-1) gives |dx|/x <= (r-1)/(r+1), and over a
    log-uniform position within the bin the mean square relative error is
    obtained by integrating; call it c(r)^2.
  * Below half the smallest level the value rounds to zero and the whole of x
    is the error.

  MSE(r,b) ~ c(r)^2 * E[x^2 . 1{x>t}]  +  E[x^2 . 1{x<t}],  t = r^-(n-1)/2

The first term falls as r falls, the second rises. The minimum is the crossover.
"""
import os, json, numpy as np, torch
from transformers import AutoModelForCausalLM
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
torch.set_grad_enabled(False)
RAT = {"shift  (2^k,   deg 1)": 2.0, "phi    (1.618, deg 2)": (1+5**0.5)/2,
       "supergold (1.4656, d3)": 1.465571231876768,
       "plastic(1.3247, deg 3)": 1.324717957244746}

def c2(r):
    """Mean square relative rounding error of a geometric ladder of ratio r.

    A value at log-position u in [0,1] across a bin sits at r^-u times the upper
    level; it rounds to whichever level is nearer, giving relative error
    |r^-u - 1| below the split and |r^-u - r^-1|/r^-1 above it. Integrating
    over u in [0,1] is one-dimensional and done numerically here rather than in
    closed form, since the split point itself depends on r."""
    u = np.linspace(0, 1, 20001)
    x = r ** (-u)                       # value, relative to the upper level 1
    err = np.minimum(np.abs(x - 1.0), np.abs(x - 1.0 / r) ) / x
    return float(np.mean(err ** 2))

print("  загружаю веса ...", flush=True)
m = AutoModelForCausalLM.from_pretrained(os.path.join(W, "smollm2"), dtype=torch.float32)
xs = []
for nm, mod in m.named_modules():
    if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm:
        w = mod.weight.data.to(torch.float64)
        s = w.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
        xs.append((w / s).abs().flatten().cpu().numpy().astype(np.float32))
x = np.concatenate(xs); del xs, m
print(f"  нормированных весов: {x.size:,}")
x2 = x.astype(np.float64) ** 2
order = np.argsort(x); xs_ = x[order]; c2s = np.cumsum(x2[order])   # для E[x^2 . 1{x<t}]
tot = c2s[-1]

def predict(r, bits):
    n = (2 ** bits - 1) // 2
    t = r ** (-(n - 1)) / 2
    i = np.searchsorted(xs_, t)
    below = c2s[i - 1] if i > 0 else 0.0
    above = tot - below
    return (c2(r) * above + below) / x.size

meas = {}
for b in (3, 4, 5):
    for nm, r in RAT.items():
        meas[(b, nm)] = predict(r, b)

# сверяю с ИЗМЕРЕННОЙ MSE прошлой итерации
measured = {(3,"shift  (2^k,   deg 1)"):6.035484e-03,(3,"phi    (1.618, deg 2)"):1.110586e-02,
 (3,"supergold (1.4656, d3)"):1.661694e-02,(3,"plastic(1.3247, deg 3)"):2.500684e-02,
 (4,"shift  (2^k,   deg 1)"):3.070406e-03,(4,"phi    (1.618, deg 2)"):1.543905e-03,
 (4,"supergold (1.4656, d3)"):1.198856e-03,(4,"plastic(1.3247, deg 3)"):1.958600e-03,
 (5,"shift  (2^k,   deg 1)"):3.069553e-03,(5,"phi    (1.618, deg 2)"):1.502649e-03,
 (5,"supergold (1.4656, d3)"):9.536284e-04,(5,"plastic(1.3247, deg 3)"):5.200983e-04}
print(f"\n  {'бит':>4} {'лестница':24} {'формула':>12} {'измерено':>12} {'отношение':>10}")
agree = 0
for b in (3,4,5):
    rows=[(nm, meas[(b,nm)], measured[(b,nm)]) for nm in RAT]
    for nm,p,mm in rows:
        print(f"  {b:4} {nm:24} {p:12.4e} {mm:12.4e} {p/mm:10.3f}")
    if min(rows,key=lambda t:t[1])[0] == min(rows,key=lambda t:t[2])[0]: agree += 1
    print(f"       формула выбирает: {min(rows,key=lambda t:t[1])[0]:24}"
          f" измерение: {min(rows,key=lambda t:t[2])[0]}")
print(f"\n  бюджетов, где формула выбрала ту же лестницу: {agree}/3")
# где формула ставит перелом по НЕПРЕРЫВНОМУ r
print("\n  оптимальное r по формуле, непрерывно:")
for b in (3,4,5,6,7,8):
    rr = np.linspace(1.02, 2.6, 800)
    vals = [predict(float(v), b) for v in rr]
    print(f"    {b} бит: r* = {rr[int(np.argmin(vals))]:.4f}")
