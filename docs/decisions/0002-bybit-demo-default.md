# ADR 0002: Bybit Demo as default exchange

## Status
Accepted (updated 2026-10)

## Context
Owner is Pakistan-based. Binance is not licensed for live use there. Bybit Demo Trading is documented and reachable via `api-demo.bybit.com`.

## Decision
Default `exchange_name=bybit` with `bybit_demo=true`. Offer Binance Spot Testnet as alternative for practice only.

**CCXT wiring:** use `enable_demo_trading(True)` / freqtrade `exchange.demo_trading: true` plus
`ccxt_config.options.enableDemoTrading: true`. Never set `hostname: "api-demo.bybit.com"` —
ccxt templates are `https://api.{hostname}`, which becomes the broken host `api.api-demo.bybit.com`.

**Modes:** `TRADING_MODE=paper` (default) keeps freqtrade `dry_run=true`. `TRADING_MODE=demo` sets
`dry_run=false` against Bybit Demo / Binance Testnet only. Mainnet requires the live lock.

## Consequences
Demo orders need Demo API keys and `TRADING_MODE=demo`. Local paper remains the zero-key default.
Document Pakistan notes in README.
