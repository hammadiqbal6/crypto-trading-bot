# Freqtrade backtest + bias analysis (sample)

**Run date:** 2026-10-18  
**Exchange data:** OKX public (Bybit geo-blocked in this environment)  
**Pairs:** BTC/USDT, ETH/USDT · **Timeframe:** 4h  
**Timerange:** ~2026-06-20 → 2026-10-18 · **dry_run**  
**Strategy:** `VolatilityMomentumStrategy`

## Backtest (honest)

| Metric | Value |
|--------|------:|
| Trades | 153 |
| Tot profit % | **-9.91%** |
| Win rate | 52.9% |
| Max drawdown | 11.10% |
| Sharpe (daily wallet) | **-2.20** |

Underperformed buy-and-hold on this window (market +35%). **No edge claimed.**

## Lookahead analysis

`has_bias = No` (0 biased signals / 20 checked).

## Recursive analysis

Incomplete: OKX 4h candle depth cannot satisfy the tool’s largest startup-candle probe (1999). Indicators use `startup_candle_count = 80` in the strategy; re-run recursive-analysis on an exchange with deeper history when available.

## Commands

```bash
pip install -e ".[engine]"
crypto-bot export-freqtrade-config
# Use a public-data exchange if Bybit is geo-blocked:
freqtrade download-data -c config/freqtrade/config.download.json --pairs BTC/USDT ETH/USDT --timeframes 4h --days 120
freqtrade backtesting -c config/freqtrade/config.backtest.json --strategy VolatilityMomentumStrategy
freqtrade lookahead-analysis -c config/freqtrade/config.backtest.json --strategy VolatilityMomentumStrategy
```
