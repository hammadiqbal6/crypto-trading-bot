# Runbook: Setup

1. `cp .env.example .env`
2. Create Bybit Demo API keys; set `BYBIT_API_KEY` / `BYBIT_API_SECRET`.
3. Optional: `GROQ_API_KEY` for LLM sentiment.
4. `pip install -e ".[engine,dev]"`
5. `make download-data && make validate`
6. `make dashboard` → open Setup wizard.
7. Keep `LIVE_TRADING=false`.
