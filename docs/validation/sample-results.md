# Sample validation results (BTC/USDT 4h)

**Run date:** 2026-10-18  
**Data:** 1000 bars via CCXT public API (Bybit geo-blocked in CI egress → **OKX** fallback)  
**Costs:** 6 bps fee + 4 bps slippage  
**Method:** walk-forward lookback selection + untouched holdout; DSR + PBO

## Headline metrics (honest)

| Metric | Value |
|--------|------:|
| Mean OOS Sharpe | **-0.98** |
| Holdout Sharpe | **-4.65** |
| Holdout return | **-2.7%** |
| Holdout max DD | **4.4%** |
| Deflated Sharpe | ~0 |
| PBO | **0.50** |
| Soft gates passed | **No** |

## Interpretation

Soft gates failed. **Do not claim an edge.** This is an expected research outcome: published momentum edges shrink after costs and OOS selection. Continue demo/paper soak; do not enable live trading.

Full JSON: regenerate anytime with `crypto-bot validate`.
