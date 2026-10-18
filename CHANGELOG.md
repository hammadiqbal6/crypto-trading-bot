# Changelog

## 0.1.0 — 2026-10-18

- Initial Signalforge / crypto-trading-bot scaffold.
- Freqtrade strategy: volatility-scaled TS + XS momentum + sentiment filter.
- News: GDELT + RSS (+ optional Reddit); sentiment FinBERT/LLM/neutral.
- Risk manager with kill switch; live trading gate.
- FastAPI dashboard (overview, news, validation, risk, logs, setup).
- Walk-forward validation with fees/slippage, DSR, PBO.
- Optional carry module (off by default).
- Docs, AGENTS.md, Cursor rules/skills/auditors, CI, Docker.
