# Changelog

## Unreleased

- Fix Bybit demo URL wiring (`enable_demo_trading` / `demo_trading`, not `hostname=api-demo.bybit.com`).
- Add `TRADING_MODE=paper|demo|live`: paper is local dry_run (default); demo hits Bybit Demo / Binance Testnet; live requires the confirm lock.
- Map `MAX_DRAWDOWN_PCT` / `MAX_DAILY_LOSS_PCT` into freqtrade MaxDrawdown + StoplossGuard protections.
- Drop redundant `strategy_path` to avoid freqtrade duplicate strategy name.

## 0.1.0 — 2026-10-18

- Initial Signalforge / crypto-trading-bot scaffold.
- Freqtrade strategy: volatility-scaled TS + XS momentum + sentiment filter.
- News: GDELT + RSS (+ optional Reddit); sentiment FinBERT/LLM/neutral.
- Risk manager with kill switch; live trading gate.
- FastAPI dashboard (overview, news, validation, risk, logs, setup).
- Walk-forward validation with fees/slippage, DSR, PBO.
- Optional carry module (off by default).
- Docs, AGENTS.md, Cursor rules/skills/auditors, CI, Docker.
