# Backtest: protections before/after (OKX public 4h, BTC/ETH/SOL)

Timerange: 2026-02-01 → 2026-10-01 · starting balance 10_000 USDT · spot

| Config | Trades | Total profit % | Max drawdown % |
|---|---:|---:|---:|
| No protections | 418 | -44.46% | 44.67% |
| MaxDrawdown 15% + daily 3% + StoplossGuard | 43 | -17.13% | 17.13% |
| MaxDrawdown 5% (tight) + daily 2% + StoplossGuard | 9 | -5.34% | 5.34% |

Protections stop new entries after the equity drawdown breach; slight overshoot past the limit is from trades already open when the lock engages.
