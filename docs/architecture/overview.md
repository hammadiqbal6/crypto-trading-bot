# Architecture overview

Signalforge wraps **freqtrade** with a research-backed strategy, news/sentiment pipeline, hard risk layer, validation suite, and FastAPI dashboard.

## Layers

1. **Config** — pydantic-settings + YAML; secrets only via env; live-trading gate.
2. **Data** — CCXT public OHLCV; optional CoinGecko.
3. **News** — GDELT, RSS, optional Reddit; pluggable `NewsSource`.
4. **Sentiment** — FinBERT → LLM (anonymised, cached, rate-limited) → neutral.
5. **Strategy** — TS momentum + XS tilt + vol targeting; sentiment as entry filter/size feature.
6. **Risk** — non-overridable gates (LLM included).
7. **Engine** — freqtrade (dependency) executes dry-run/demo orders.
8. **Validation** — walk-forward, holdout, DSR, PBO; FT lookahead/recursive.
9. **UI/API** — FastAPI + Jinja dashboard for ops/onboarding.

## Process model

- Dashboard process can refresh news/sentiment and write `user_data/sentiment_features.json`.
- Freqtrade process reads that file + OHLCV and places dry-run/demo trades.
- Optional compose profile `trade` runs freqtrade alongside the dashboard.
