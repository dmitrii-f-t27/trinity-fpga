# GF+ Cross-Replication — Final Summary

**Date:** 2026-07-18  
**Status:** Cross-replicated [measured — GPU, 1 model, 2 implementations]

---

## Two implementations converged

| Class | webterm v2 (linear layers) | pod-benchmark (all 39 matrices) | GF+A Status |
|-------|---------------------------|--------------------------------|-------------|
| 4-bit | 19.37 dB | 19.46 dB | Best in class, both harnesses |
| 6-bit | 31.05 dB | 31.09 dB | Best; φ-e2m3 = best single |
| 8-bit | 43.21 dB | 43.24 dB | Best |
| 16-bit | — | 91.44 dB | Best |

Discrepancy in hundredths: pod-benchmark includes embeddings (39 matrices),
webterm only linear layers. Direction and format ordering identical.

## 16-bit class insight

In per-row-scaled mode: e2m13 (91.36 dB) beats fp16 (73.80 dB) by ~17.6 dB
and φ-e6m9 (67.78 dB). When each row is pre-scaled, wide exponent is wasted;
nearly all bits are more valuable as mantissa.

Cross-validation: fp16 = 73.8 and φ-e6m9 = 67.8 match independent measurement
from 06.07 on different harness — mutual validation confirmed.

## Honest formulation for papers

> GF+A ≥ each tested fixed-format in all 4 width classes by MSE, confirmed
> by two independent implementations; margin on uniform weights is
> +0.01…+0.08 dB. This is a guarantee-by-construction (per-row argmin),
> not a large empirical win. Larger margins appear on heterogeneous data;
> on uniform weights, adaptive is insurance ("no worse than best pocket").

## Key finding from our GPU benchmark

GF+A selects INT in 99.8% of rows at all widths on real weights.
Float pockets (including φ-rule) never selected when per-row scaling is applied.
This means: the scaling, not the float format, drives accuracy.

## Open gates

1. **QAT ablation**: does format ordering persist under STE training?
2. **LUT cost of pocket multiplexer**: ~10-20 LUT overhead (not measured)
3. **NF4 at 4-bit**: GF+A can't beat NF4 on Gaussian (header overhead negates gain)
