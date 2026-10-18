# ADR 0002: Bybit Demo as default exchange

## Status
Accepted

## Context
Owner is Pakistan-based. Binance is not licensed for live use there. Bybit Demo Trading is documented and reachable via `api-demo.bybit.com`.

## Decision
Default `exchange_name=bybit` with `bybit_demo=true`. Offer Binance Spot Testnet as alternative for practice only.

## Consequences
CCXT hostname overrides for demo; document Pakistan notes in README.
