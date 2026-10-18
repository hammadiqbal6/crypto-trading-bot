# Validation methodology

## Goals
Reduce data-snooping and overconfidence (Bailey et al.; McLean & Pontiff).

## Pipeline
1. Download public OHLCV (CCXT) — no key.
2. **Walk-forward**: rolling train/test; select lookback by IS Sharpe; record OOS Sharpe after fees (6 bps) + slippage (4 bps).
3. **Untouched holdout**: final bars never used for selection.
4. **Deflated Sharpe (DSR)** adjusting for number of trials.
5. **PBO** estimate across folds.
6. Soft gates: mean OOS Sharpe > 0, DSR > 0.5, PBO < 0.5, holdout Sharpe > 0.
7. Freqtrade `lookahead-analysis` and `recursive-analysis` on the IStrategy.
8. 4–8 weeks demo/paper matching before any live consideration.

## Honesty
Failing gates is a valid research outcome. Do not tune until holdout “works” without a new holdout.
