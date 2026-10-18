# Skill: Run backtest / walk-forward validation

1. `crypto-bot download-data` (CCXT public).
2. `crypto-bot validate` — walk-forward + holdout with fees/slippage, DSR, PBO.
3. Export config: `crypto-bot export-freqtrade-config`.
4. `freqtrade backtesting -c config/freqtrade/config.json --strategy VolatilityMomentumStrategy`
5. `freqtrade lookahead-analysis` and `recursive-analysis`.
6. Record metrics honestly in PR/docs — do not claim edge if gates fail.
7. Prefer untouched holdout after any LLM/feature cutoff date when using LLM labels.
