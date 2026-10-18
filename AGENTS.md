# AGENTS.md — Signalforge / crypto-trading-bot

Rules for any AI agent (or human) continuing this codebase.

## Mission

Build and maintain a **demo/paper-first** AI crypto trading bot. Honest accuracy over hype. Follow `docs/research/ai-trading-research.md` and owner requirements in `docs/research/owner-requirements.md`.

## Do

- Keep **live trading off by default**; require `LIVE_TRADING` + `LIVE_TRADING_CONFIRM=I_UNDERSTAND_LIVE_RISK`.
- Treat LLM/sentiment as a **feature/filter only** — never place orders directly; never override `RiskManager`.
- Prefer modular layers: `config` → `data/news/sentiment` → `strategies` → `risk` → freqtrade engine → `api/dashboard`.
- Use typed Python, pydantic settings, structlog, pytest, ruff, mypy.
- Handle edge cases with **actionable guidance** in UI + logs (missing keys, rate limits, empty data, LLM failure → FinBERT/neutral).
- Commit/push small logical chunks; update docs when behaviour changes.
- Surface validation metrics (walk-forward, holdout, fees, DSR, PBO) without overstating edge.

## Don't

- Don't vendor freqtrade — depend on it (`pip install -e ".[engine]"`).
- Don't commit `.env`, keys, or real credentials.
- Don't claim >55% daily directional accuracy without rigorous OOS proof.
- Don't enable carry or FreqAI by default.
- Don't bypass kill switch / daily loss / max trades / stoploss.
- Don't use vision-LLMs on chart screenshots as a signal source.

## Commands

| Task | Command |
|---|---|
| Install | `pip install -e ".[engine,dev]"` |
| Lint | `make lint` |
| Types | `make typecheck` |
| Tests | `make test` |
| Dashboard | `make dashboard` |
| Validate | `make validate` |
| Download data | `make download-data` |
| Export FT config | `make export-config` |

## Architecture (short)

- `src/crypto_bot/config` — settings + live gate
- `src/crypto_bot/news` — GDELT/RSS/Reddit
- `src/crypto_bot/sentiment` — FinBERT + LLM + cache
- `src/crypto_bot/strategies` — signal math
- `user_data/strategies/VolatilityMomentumStrategy.py` — freqtrade strategy
- `src/crypto_bot/risk` — hard gates
- `src/crypto_bot/validation` — walk-forward / DSR / PBO
- `src/crypto_bot/api` + `dashboard` — FastAPI UI
- `src/crypto_bot/carry` — optional funding/basis

## Skills & auditors

See `.cursor/skills/` for recurring tasks and `.cursor/agents/` for auditor personas (code, risk, backtest-validity, UI QA, docs).

## Testing expectations

- Unit tests for risk, signals, metrics, sentiment fallbacks, settings gate.
- Integration tests for API/dashboard pages.
- E2E (Playwright) for critical UI flows when changing the dashboard.
- Run a sample validation on public CCXT data before claiming readiness.
