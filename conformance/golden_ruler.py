#!/usr/bin/env python3
"""
Golden Ruler — Format Selection Tool for Hardware Engineers

Input: workload requirements
Output: ranked format recommendations with justification

Usage:
  python3 conformance/golden_ruler.py --range 1e-6..1e6 --precision 0.001 --width 16 --dsp available
  python3 conformance/golden_ruler.py --task llm-training --width 16
  python3 conformance/golden_ruler.py --task inference --width 8
  python3 conformance/golden_ruler.py --list
"""
import sys, math, argparse, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import all oracles
FORMATS = {}
for mod_name in ['gf_ref','ieee_ref','bf16_ref','fp8_ref','takum_ref','tekum_ref',
                 'posit_ref','decimal_ref','mxfp_ref','legacy_ref','lns_ref',
                 'int_ref','nf4_ref','gfternary_ref','extended_ref']:
    try:
        mod = __import__(mod_name)
        for name, fmt in mod.FORMATS.items():
            w = getattr(fmt, 'width', getattr(fmt, 'n', getattr(fmt, 'bits', 0)))
            if w > 0:
                e = getattr(fmt, 'exp_bits', 0)
                m = getattr(fmt, 'mant_bits', 0)
                bias = getattr(fmt, 'bias', 0)
                FORMATS[name] = {'width': w, 'E': e, 'M': m, 'bias': bias, 'module': mod_name}
    except:
        pass

# LUT scaling coefficients (measured)
LUT_ADD_C = 1.55
LUT_MUL_C = 2.06

def estimate_lut(width, op='add'):
    c = LUT_ADD_C if op == 'add' else LUT_MUL_C
    return int(c * width**2)

def dynamic_range_decades(E, bias):
    if E == 0: return 0
    exp_max = (1 << E) - 1
    # range from min denormal to max normal
    max_exp = exp_max - bias
    min_exp = 1 - bias - 1  # denormal
    return abs(max_exp - min_exp) * math.log10(2)

def precision_digits(M):
    return M * math.log10(2)

def gradient_survival(M):
    """Estimate % of gradient updates that survive quantization"""
    if M == 0: return 0
    step_at_half = 2**(-(M+1)) * 0.5
    if step_at_half < 1e-10: return 100.0
    # Typical gradient: N(0.0001, 0.001)
    # Survival = P(|grad| > step)
    from statistics import NormalDist
    nd = NormalDist(0.0001, 0.001)
    survival = 1 - nd.cdf(step_at_half) + nd.cdf(-step_at_half)
    return survival * 100

def score_format(name, fmt_info, requirements):
    """Score a format against requirements. Higher = better match."""
    score = 0
    reasons = []
    w = fmt_info['width']
    E = fmt_info['E']
    M = fmt_info['M']
    
    # Width constraint
    max_w = requirements.get('max_width', 64)
    if w > max_w:
        return -999, [f"width {w} > max {max_w}"]
    if w <= max_w:
        score += 10
    
    # Dynamic range requirement
    min_range = requirements.get('min_range_decades', 0)
    actual_range = dynamic_range_decades(E, fmt_info['bias'])
    if actual_range >= min_range:
        score += 20
        reasons.append(f"range {actual_range:.0f}dec ≥ {min_range}")
    else:
        score -= 50
        reasons.append(f"range {actual_range:.0f}dec < {min_range} ✗")
    
    # Precision requirement
    min_digits = requirements.get('min_precision_digits', 0)
    actual_digits = precision_digits(M)
    if actual_digits >= min_digits:
        score += 15
        reasons.append(f"prec {actual_digits:.1f}d ≥ {min_digits}")
    else:
        score -= 30
        reasons.append(f"prec {actual_digits:.1f}d < {min_digits} ✗")
    
    # LUT cost (lower = better)
    lut_add = estimate_lut(w, 'add')
    lut_mul = estimate_lut(w, 'mul')
    if lut_add < 500: score += 10
    elif lut_add < 2000: score += 5
    elif lut_add > 50000: score -= 20
    reasons.append(f"LUT add≈{lut_add} mul≈{lut_mul}")
    
    # Gradient survival (for training tasks)
    if requirements.get('task') in ['llm-training', 'training']:
        gs = gradient_survival(M)
        if gs > 50: score += 20
        elif gs > 10: score += 10
        elif gs < 1: score -= 30
        reasons.append(f"grad survival {gs:.0f}%")
    
    # Robustness bonus
    if E >= 6 and M >= 9:
        score += 15
        reasons.append("7/7 ROBUST ✓")
    elif E >= 5 and M >= 7:
        score += 5
        reasons.append("partial robust")
    elif E < 4 or M < 4:
        score -= 10
        reasons.append("FRAGILE")
    
    return score, reasons

TASKS = {
    'llm-training': {'max_width': 32, 'min_range_decades': 10, 'min_precision_digits': 2.5, 'task': 'llm-training'},
    'inference': {'max_width': 16, 'min_range_decades': 5, 'min_precision_digits': 1.5},
    'edge-ml': {'max_width': 8, 'min_range_decades': 3, 'min_precision_digits': 1.0},
    'scientific': {'max_width': 128, 'min_range_decades': 40, 'min_precision_digits': 6.0},
    'dsp': {'max_width': 32, 'min_range_decades': 20, 'min_precision_digits': 4.0},
    'fpga-minimal': {'max_width': 16, 'min_range_decades': 15, 'min_precision_digits': 2.5},
}

def main():
    parser = argparse.ArgumentParser(description="Golden Ruler — Format Selection Tool")
    parser.add_argument('--task', choices=list(TASKS.keys()), help='Predefined workload')
    parser.add_argument('--max-width', type=int, help='Maximum bit width')
    parser.add_argument('--min-range', type=float, help='Minimum dynamic range (decades)')
    parser.add_argument('--min-precision', type=float, help='Minimum precision (decimal digits)')
    parser.add_argument('--list', action='store_true', help='List all formats with properties')
    parser.add_argument('--top', type=int, default=10, help='Show top N recommendations')
    args = parser.parse_args()
    
    if args.list:
        print(f"\n{'Format':<16} {'W':>3} {'E':>3} {'M':>3} {'Range(dec)':>10} {'Prec(d)':>7} {'LUT(add)':>8} {'Grad%':>6}")
        print("-" * 65)
        for name in sorted(FORMATS, key=lambda n: FORMATS[n]['width']):
            f = FORMATS[name]
            r = dynamic_range_decades(f['E'], f['bias'])
            p = precision_digits(f['M'])
            l = estimate_lut(f['width'], 'add')
            g = gradient_survival(f['M'])
            print(f"{name:<16} {f['width']:>3} {f['E']:>3} {f['M']:>3} {r:>10.1f} {p:>7.1f} {l:>8} {g:>5.0f}%")
        return
    
    # Build requirements
    req = {}
    if args.task:
        req = dict(TASKS[args.task])
    if args.max_width:
        req['max_width'] = args.max_width
    if args.min_range:
        req['min_range_decades'] = args.min_range
    if args.min_precision:
        req['min_precision_digits'] = args.min_precision
    if not req:
        req = {'max_width': 64, 'min_range_decades': 5, 'min_precision_digits': 2.0}
    
    print(f"\n{'='*70}")
    print(f"GOLDEN RULER — Format Recommendation")
    print(f"{'='*70}")
    print(f"Requirements: {req}")
    print()
    
    # Score all formats
    scored = []
    for name, info in FORMATS.items():
        score, reasons = score_format(name, info, req)
        if score > -100:
            scored.append((name, info, score, reasons))
    
    scored.sort(key=lambda x: -x[2])
    
    print(f"{'Rank':>4} {'Format':<16} {'W':>3} {'Score':>6} {'Reasons'}")
    print("-" * 80)
    for i, (name, info, score, reasons) in enumerate(scored[:args.top]):
        reason_str = "; ".join(reasons[:4])
        print(f"{i+1:>4} {name:<16} {info['width']:>3} {score:>6} {reason_str}")
    
    if scored:
        best = scored[0]
        print(f"\n✓ RECOMMENDED: {best[0]} (score {best[2]})")
        print(f"  Width: {best[1]['width']} bits, E={best[1]['E']}, M={best[1]['M']}")
        est_lut = estimate_lut(best[1]['width'], 'add')
        print(f"  Estimated LUT: ~{est_lut} (add), ~{estimate_lut(best[1]['width'], 'mul')} (mul)")
        r = dynamic_range_decades(best[1]['E'], best[1]['bias'])
        p = precision_digits(best[1]['M'])
        print(f"  Dynamic range: {r:.1f} decades, Precision: {p:.1f} digits")

if __name__ == '__main__':
    main()
