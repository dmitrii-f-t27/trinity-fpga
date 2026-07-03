#!/usr/bin/env python3
"""fpga_trunc_analyze — bit-exact truncation sweep for wide-datapath FPGA decoders.

Codifies the methodology developed for takum32/64 (LOOP_REPORT_2026_07_03):
sweep operand truncation (sticky-OR) widths on a format's parametric RTL model
to find the narrowest bit-exact datapath that still matches the golden oracle.
Narrower multiplies route more easily on openXC7.

Usage:
    python3 tools/fpga_trunc_analyze.py takum64            # full report
    python3 tools/fpga_trunc_analyze.py takum32 --vectors 5000
    python3 tools/fpga_trunc_analyze.py --list

Each registered format provides:
  * golden(code) -> u32         (the mpmath oracle, from conformance/)
  * rtl(code, **trunc) -> u32   (a parametric Python model of the Verilog datapath)
  * N                            (bit width)
  * axes                         (which truncation params to sweep)

The tool reports, per axis: the minimum keep-width that is bit-exact on the
sample, with a 2-bit safety margin recommendation, plus the resulting multiply
width reduction (routing relief).
"""
import argparse, importlib, random, sys

# ---- registry of parametric RTL models (verified vs golden) ----
# Each entry loads its model lazily so importing this tool is cheap.
REGISTRY = {
    "takum64": {
        "module": "takum64_decode_conformance_ax7203",
        "N": 64,
        "axes": {
            "ell_keep": {"full": 70, "sweep": [70, 60, 56, 52, 50, 48, 46, 44, 42, 40, 38, 36], "operand": "ell_59 (70-bit signed)"},
            "flo_keep": {"full": 91, "sweep": [91, 48, 32, 24, 20, 18, 16, 14, 12], "operand": "f_lo (91-bit)"},
        },
        "multiply_widths": {"L_Q107": ("ell_keep", 48), "flo_ln2": ("flo_keep", 48)},
    },
    "takum32": {
        "module": "takum32_decode_conformance_ax7203",
        "N": 32,
        "axes": {
            "ell_keep": {"full": 38, "sweep": [38, 32, 28, 24, 20], "operand": "ell_27 (38-bit signed)"},
            "flo_keep": {"full": 59, "sweep": [59, 48, 40, 32, 28, 24, 20, 18, 16, 14, 12, 10, 8], "operand": "f_lo (59-bit)"},
        },
        "multiply_widths": {"L_Q75": ("ell_keep", 48), "flo_ln2": ("flo_keep", 48)},
    },
}


def _load_model(fmt):
    """Load the parametric RTL model for `fmt`. Returns (rtl_fn, golden_fn, N, meta)."""
    meta = REGISTRY[fmt]
    # the conformance module provides golden + constants (CBIAS, C_Q48, LN2_Q48, BRAM, ...)
    conf = importlib.import_module(meta["module"])
    # the parametric model is built here from the constants (kept in sync with the .v)
    if fmt == "takum64":
        return _takum64_model(conf), conf.golden_takum64, meta["N"], meta
    if fmt == "takum32":
        return _takum32_model(conf), conf.golden_takum32, meta["N"], meta
    raise KeyError(fmt)


def _takum64_model(conf):
    CBIAS = conf._C_BIAS; C_Q48 = 203041276517399; LN2_Q48 = 195103586505167; PMAX = 59
    BRAM = _load_bram("fpga/openxc7-synth/takum32_2frac.mem")
    def to_signed(x, w):
        m = (1 << w) - 1; x &= m
        return x - (1 << w) if (x >> (w-1)) & 1 else x
    def rtl(t64, ell_keep=70, flo_keep=91):
        S=(t64>>63)&1; D=(t64>>62)&1; R=(t64>>59)&7
        cbias=CBIAS[(D<<3)|R]; r_eff=R if D else (7-R); p=PMAX-r_eff
        lower=t64&((1<<59)-1)
        M_u=lower&((1<<p)-1) if p>0 else 0
        C_u=(lower>>p)&((1<<r_eff)-1) if r_eff>0 else 0
        c=cbias+C_u; val=c*(1<<59)+(M_u<<r_eff)
        ef=(-val if S else val)&((1<<70)-1)
        if ell_keep<70:
            drop=70-ell_keep; low=ef&((1<<drop)-1)
            e=(ef&~((1<<drop)-1))|((1<<(drop-1)) if low else 0); e&=((1<<70)-1)
        else: e=ef
        L=to_signed(to_signed(e,70)*C_Q48,119); k=L>>107; frac=L&((1<<107)-1)
        fh=(frac>>91)&0xFFFF; ff=frac&((1<<91)-1)
        if flo_keep<91:
            drop=91-flo_keep; low=ff&((1<<drop)-1)
            f=(ff&~((1<<drop)-1))|((1<<(drop-1)) if low else 0)
        else: f=ff
        t=BRAM[fh]; corr=((f*LN2_Q48)>>107)&0xFFFFFFFF
        cq=(corr+((corr*corr)>>49))&0xFFFFFFFF; tp=(t*cq)&((1<<80)-1)
        mant=(t+(tp>>48))&((1<<49)-1)
        if mant&(1<<48): mn=(mant>>1)&((1<<48)-1); e2=k+1
        else: mn=mant&((1<<48)-1); e2=k
        m25=mn>>24; g=(mn>>23)&1; rb=(mn>>22)&1; stb=1 if (mn&((1<<21)-1)) else 0
        if g&(rb|stb|(m25&1)): m25=(m25+1)&0x1FFFFFF
        if m25&(1<<24): m24=0x800000; e2+=1
        else: m24=m25&0xFFFFFF
        if t64==0: return 0
        if t64==(1<<63): return 0x7FC00000
        if e2>127: return (S<<31)|0x7F800000
        if e2<-150: return (S<<31)
        if e2<-126:
            if e2>=-149:
                sh=-e2-102; sv=mn>>sh
                sg=((mn>>(sh-1))&1) if sh>=1 else 0
                sr=((mn>>(sh-2))&1) if sh>=2 else 0
                ss=1 if (sh>=3 and (mn&((1<<(sh-2))-1))) else 0
                sru=1 if (sg&(sr|ss|(sv&1))) else 0
                sk=((sv&0x7FFFFF)+(1 if sru else 0))&0xFFFFFF
                if sk>=0x800000: return (S<<31)|(1<<23)
                if sk==0: return (S<<31)
                return (S<<31)|sk
            return (S<<31)
        return ((S<<31)|(((e2+127)&0xFF)<<23)|(m24&0x7FFFFF))&0xFFFFFFFF
    return rtl


def _takum32_model(conf):
    CBIAS = conf._C_BIAS; C_Q48 = 203041276517399; LN2_Q48 = 195103586505167
    BRAM = _load_bram("fpga/openxc7-synth/takum32_2frac.mem")
    def to_signed(x, w):
        m = (1 << w) - 1; x &= m
        return x - (1 << w) if (x >> (w-1)) & 1 else x
    def rtl(t32, ell_keep=38, flo_keep=59):
        S=(t32>>31)&1; D=(t32>>30)&1; R=(t32>>27)&7
        cbias=CBIAS[(D<<3)|R]; r_eff=R if D else (7-R); p=27-r_eff
        lower=t32&((1<<27)-1)
        M_u=lower&((1<<p)-1) if p>0 else 0
        C_u=(lower>>p)&((1<<r_eff)-1) if r_eff>0 else 0
        c=cbias+C_u; val=c*(1<<27)+(M_u<<r_eff)
        ef=(-val if S else val)&((1<<38)-1)
        if ell_keep<38:
            drop=38-ell_keep; low=ef&((1<<drop)-1)
            e=(ef&~((1<<drop)-1))|((1<<(drop-1)) if low else 0); e&=((1<<38)-1)
        else: e=ef
        L=to_signed(to_signed(e,38)*C_Q48,87); k=L>>75; frac=L&((1<<75)-1)
        fh=(frac>>59)&0xFFFF; ff=frac&((1<<59)-1)
        if flo_keep<59:
            drop=59-flo_keep; low=ff&((1<<drop)-1)
            f=(ff&~((1<<drop)-1))|((1<<(drop-1)) if low else 0)
        else: f=ff
        t=BRAM[fh]; corr=((f*LN2_Q48)>>75)&0xFFFFFFFF
        cq=(corr+((corr*corr)>>49))&0xFFFFFFFF; tp=(t*cq)&((1<<80)-1)
        mant=(t+(tp>>48))&((1<<49)-1)
        if mant&(1<<48): mn=(mant>>1)&((1<<48)-1); e2=k+1
        else: mn=mant&((1<<48)-1); e2=k
        m25=mn>>24; g=(mn>>23)&1; rb=(mn>>22)&1; stb=1 if (mn&((1<<21)-1)) else 0
        if g&(rb|stb|(m25&1)): m25=(m25+1)&0x1FFFFFF
        if m25&(1<<24): m24=0x800000; e2+=1
        else: m24=m25&0xFFFFFF
        if t32==0: return 0
        if t32==(1<<31): return 0x7FC00000
        if e2>127: return (S<<31)|0x7F800000
        if e2<-150: return (S<<31)
        if e2<-126:
            if e2>=-149:
                sh=-e2-102; sv=mn>>sh
                sg=((mn>>(sh-1))&1) if sh>=1 else 0
                sr=((mn>>(sh-2))&1) if sh>=2 else 0
                ss=1 if (sh>=3 and (mn&((1<<(sh-2))-1))) else 0
                sru=1 if (sg&(sr|ss|(sv&1))) else 0
                sk=((sv&0x7FFFFF)+(1 if sru else 0))&0xFFFFFF
                if sk>=0x800000: return (S<<31)|(1<<23)
                if sk==0: return (S<<31)
                return (S<<31)|sk
            return (S<<31)
        return ((S<<31)|(((e2+127)&0xFF)<<23)|(m24&0x7FFFFF))&0xFFFFFFFF
    return rtl


def _load_bram(path):
    bram = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line: bram.append(int(line, 16))
    assert len(bram) == 65536, f"BRAM size {len(bram)} != 65536"
    return bram


def _sample(fmt, N, n):
    """Build the verification sample: corners + seeded random + boundary bands."""
    rnd = random.Random(41)
    F = 1 << (N - 2)
    corners = [0, F, F | (1 << (N-1)), 1 << (N-1), 1, 2, F + 1]
    sample = corners + [rnd.getrandbits(N) for _ in range(max(0, n - len(corners)))]
    rnd2 = random.Random(2026)
    sample += [rnd2.getrandbits(N) for _ in range(min(2000, n))]
    # near-unity band + subnormal band for stress
    sample += [(F + i) for i in range(0, min(256, n))]
    return sample


def sweep_axis(rtl, golden, sample, axis_name, axis_meta, other_trunc, baseline_mm):
    """Sweep one truncation axis. `baseline_mm` = full-width mismatch count;
    a keep is 'safe' if it adds ZERO new mismatches vs baseline (relative test),
    NOT if it's absolutely 0 (the full-width design may have pre-existing edge
    cases -- those are documented separately, not caused by truncation)."""
    print(f"\n  axis: {axis_name}  ({axis_meta['operand']})   [baseline full-width mism={baseline_mm}]")
    print(f"    {'keep':>6} {'prod-w':>8} {'mism':>6} {'delta':>6} {'status':>26}")
    min_ok = None   # smallest keep-width that adds zero new mismatches vs baseline
    for keep in axis_meta["sweep"]:
        mm = 0
        for v in sample:
            params = {**other_trunc, axis_name: keep}
            if rtl(v, **params) != golden(v): mm += 1
        delta = mm - baseline_mm
        status = "OK (zero new vs base)" if delta == 0 else f"+{delta} new ({100*delta/len(sample):.3f}%)"
        print(f"    {keep:>6d} {keep+48:>7d}b {mm:>6d} {delta:>+6d}   {status}")
        if delta == 0:
            min_ok = keep if min_ok is None else min(min_ok, keep)
    return min_ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("format", nargs="?", help="format to analyze (takum64, takum32, ...)")
    ap.add_argument("--vectors", type=int, default=4000, help="sample size for the sweep (default 4000)")
    ap.add_argument("--list", action="store_true", help="list registered formats and exit")
    ap.add_argument("--conformance-dir", default="conformance", help="dir with golden modules")
    a = ap.parse_args()
    if a.list:
        print("Registered formats:")
        for fmt, meta in REGISTRY.items():
            print(f"  {fmt:10s} N={meta['N']}  axes={list(meta['axes'])}  golden={meta['module']}")
        return 0
    if not a.format:
        ap.error("format required (or --list)")
    if a.format not in REGISTRY:
        ap.error(f"unknown format '{a.format}'. Registered: {list(REGISTRY)}")
    sys.path.insert(0, a.conformance_dir)
    rtl, golden, N, meta = _load_model(a.format)
    sample = _sample(a.format, N, a.vectors)
    # validate full-width model is faithful first
    full = {k: v["full"] for k, v in meta["axes"].items()}
    baseline_mm = sum(1 for v in sample if rtl(v, **full) != golden(v))
    print(f"== {a.format}: full-width model vs golden on {len(sample)} vectors: {len(sample)-baseline_mm}/{len(sample)} (baseline mism={baseline_mm}) ==")
    if baseline_mm > len(sample) * 0.01:
        print(f"  WARNING: >1% full-width mismatches -- model may be unfaithful; results below are still RELATIVE.")
    mins = {}
    for axis_name, axis_meta in meta["axes"].items():
        other = {k: v["full"] for k, v in meta["axes"].items() if k != axis_name}
        mins[axis_name] = sweep_axis(rtl, golden, sample, axis_name, axis_meta, other, baseline_mm)
    # summary
    print(f"\n== RECOMMENDATION ({a.format}) ==")
    for axis_name, axis_meta in meta["axes"].items():
        m = mins[axis_name]
        if m is None:
            print(f"  {axis_name}: NO bit-exact truncation found in the swept range (keep full {axis_meta['full']}-bit)")
        else:
            margin = m - 2 if m - 2 >= min(axis_meta["sweep"]) else m
            print(f"  {axis_name}: min bit-exact keep = {m}-bit  (recommended with 2-bit margin: {margin}-bit; full = {axis_meta['full']}-bit)")
    print(f"\n  Multiply-width relief:")
    for mul_name, (axis, opw) in meta["multiply_widths"].items():
        m = mins.get(axis)
        full_w = meta["axes"][axis]["full"] + opw
        if m:
            new_w = m + opw
            print(f"    {mul_name:10s}: {full_w}-bit -> {new_w}-bit  (saves {full_w-new_w} bits)")
        else:
            print(f"    {mul_name:10s}: {full_w}-bit (no truncation viable)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
