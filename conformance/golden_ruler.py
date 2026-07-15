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
                # Tapered formats: assign effective E/M near unity
                name_lower = name.lower()
                if 'posit' in name_lower and e == 0:
                    es = getattr(fmt, 'es', 2)
                    e = es + 2  # regime contributes ~2 effective exp bits near unity
                    m = w - 1 - 3 - es  # S + regime(~3) + es exponent
                    bias = (1 << (e - 1)) - 1 if e > 0 else 0
                elif ('takum' in name_lower or 'tekum' in name_lower) and e == 0:
                    e = 5  # takum effective exponent near unity (S+D+R3+char ≈ 5 overhead)
                    m = w - 1 - 5  # remaining bits = mantissa
                    bias = (1 << (e - 1)) - 1 if e > 0 else 0
                FORMATS[name] = {'width': w, 'E': e, 'M': m, 'bias': bias, 'module': mod_name}
    except:
        pass

# LUT scaling coefficients (measured)
LUT_ADD_C = 1.55
LUT_MUL_C = 2.06

def estimate_lut(width, op='add'):
    c = LUT_ADD_C if op == 'add' else LUT_MUL_C
    return int(c * width**2)

# Known dynamic ranges for tapered formats (from empirical testing)
TAPERED_RANGES = {
    'posit8': 10, 'posit16': 30, 'posit32': 80, 'posit64': 200,
    'takum8': 40, 'takum16': 83, 'takum32': 153, 'takum64': 320,
    'tekum8': 40, 'tekum16': 153, 'tekum32': 300,
}

def dynamic_range_decades(E, bias, name=''):
    if name.lower() in TAPERED_RANGES:
        return TAPERED_RANGES[name.lower()]
    if E == 0: return 0
    exp_max = (1 << E) - 1
    max_exp = exp_max - bias
    min_exp = 1 - bias - 1
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

def effective_mantissa(name, fmt_info):
    """Get EFFECTIVE mantissa bits (handles tapered formats correctly)"""
    name_lower = name.lower()
    if 'posit' in name_lower:
        n = fmt_info.get('width', 16)
        # posit has variable mantissa; near unity: M ≈ n - 4 (sign + regime + 2 exp)
        return max(n - 4, 4)
    elif 'takum' in name_lower or 'tekum' in name_lower:
        n = fmt_info.get('width', 16)
        # takum has variable mantissa; near unity: M ≈ n - 5 (S + D + R3 + char)
        return max(n - 5, 4)
    else:
        return fmt_info.get('M', 0)

def score_format(name, fmt_info, requirements):
    """Score a format against requirements. Higher = better match."""
    score = 0
    reasons = []
    name_lower = name.lower()
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
    actual_range = dynamic_range_decades(E, fmt_info['bias'], name)
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
        M_eff = effective_mantissa(name, fmt_info)
        gs = gradient_survival(M_eff)
        if gs > 50: score += 20
        elif gs > 10: score += 10
        elif gs < 1: score -= 30
        reasons.append(f"grad survival {gs:.0f}%")
    
    # Robustness bonus (from MEASURED benchmark, not heuristic)
    ROBUST_FORMATS = {
        'gf14': 7, 'gf16': 7, 'gf20': 7, 'gf24': 7, 'gf32': 7, 'gf48': 7, 'gf64': 7,
        'posit16': 7, 'posit32': 7, 'posit64': 7,
        'takum16': 7, 'takum32': 7, 'takum64': 7,
        'tekum16': 7, 'tekum32': 7,
        'afp': 7, 'bfloat16': 4, 'binary32': 7, 'binary64': 7,
        'gf12': 5, 'binary16': 6,
        'gf10': 2,
        'gf8': 0, 'gf6': 0, 'gf4': 0, 'fp8_e4m3': 0, 'fp8_e5m2': 0,
    }
    robust_score = ROBUST_FORMATS.get(name_lower, -1)
    if robust_score == 7:
        score += 15
        reasons.append("7/7 ROBUST ✓")
    elif robust_score >= 4:
        score += 5
        reasons.append(f"{robust_score}/7 partial")
    elif robust_score <= 1:
        score -= 10
        reasons.append(f"{robust_score}/7 FRAGILE")
    
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
            r = dynamic_range_decades(f['E'], f['bias'], name)
            p = precision_digits(f['M'])
            l = estimate_lut(f['width'], 'add')
            g = gradient_survival(effective_mantissa(name, f))
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
    
    # Sort by score, then by gradient survival (for training tasks)
    def sort_key(entry):
        name, info, score, reasons = entry
        M_eff = effective_mantissa(name, info)
        gs = gradient_survival(M_eff)
        return (-score, -gs)
    scored.sort(key=sort_key)
    
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
        r = dynamic_range_decades(best[1]['E'], best[1]['bias'], best[0])
        p = precision_digits(best[1]['M'])
        print(f"  Dynamic range: {r:.1f} decades, Precision: {p:.1f} digits")

if __name__ == '__main__':
    main()
