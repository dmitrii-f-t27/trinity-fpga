# Why the network prefers a coarser ladder than mean squared error does

The closed form of T33 ranked the ladders correctly at three and five bits and
transposed the top pair at four -- picking supergolden where perplexity picked
`phi`. The transposition reproduced on both models, in the same direction, which
makes it an effect rather than noise. This explains it.

## The mechanism

Plain MSE treats every weight alike. The output error of a linear layer is
`sum_j dw_ij x_j`, so a weight multiplying a large input channel costs more than
one multiplying a small channel, and the two are not close: measuring the RMS of
every input channel of every linear layer of SmolLM2-135M, the first attention
projection alone spans **28x** between its largest channel and its median.

This is the observation AWQ is built on -- weight salience follows the
*activation* distribution, not the weight distribution, and protecting roughly
1% of channels recovers most of the quantisation loss. AWQ uses it to choose a
per-channel scaling. The same observation chooses a ladder.

## The test

Rank the ladders by `sum_j a_j^2 dw_ij^2`, with `a_j` the RMS of input channel
`j`, instead of by `sum dw^2`. On SmolLM2-135M:

| bits | by MSE | by activation-weighted error | by perplexity |
|---|---|---|---|
| 4 | supergolden | **phi** | **phi** |
| 5 | plastic | plastic | plastic |

| bits | ladder | MSE | activation-weighted |
|---|---|---|---|
| 4 | shift | 3.0704e-03 | 3.3271e-04 |
| 4 | **phi** | 1.5439e-03 | **1.8241e-04** |
| 4 | supergolden | **1.1989e-03** | 1.9152e-04 |
| 4 | plastic | 1.9586e-03 | 4.6470e-04 |
| 5 | phi | 1.5026e-03 | 1.6214e-04 |
| 5 | supergolden | 9.5363e-04 | 1.0291e-04 |
| 5 | **plastic** | **5.2010e-04** | **5.7746e-05** |

The weighting reverses the four-bit pair and leaves five bits alone, which is
exactly the correction needed. The two ladders it separates differ by 5% in
activation-weighted error and by 22% in plain error -- the outlier channels are
what turns the second number into the first.

## Why it lands on the coarse side

A finer ladder spends its codes on resolution and loses span. The weights that
sit near the top of their channel's range are exactly the ones a coarse ladder
still represents and a fine ladder must clip, and those are disproportionately
the weights that multiply large activations. So the penalty for going fine is
concentrated precisely where the network is most sensitive, and plain MSE, which
spreads it evenly, understates it.

**T34 (the salience correction).** Among multiply-free ladders at a fixed code
budget, the minimiser of activation-weighted quantisation error
`sum_j a_j^2 dw_ij^2` predicts the perplexity ranking where plain mean squared
error does not. The correction always moves the choice toward the coarser
ladder, because span is what protects the salient weights.

## What this changes for the alphabet

`phi` is not merely tied at four bits and lucky. It is the predicted optimum
once weights are weighted by what they multiply, and the prediction now agrees
with the measurement on the budget this work targets.
