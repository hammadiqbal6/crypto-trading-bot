# Runbook: Troubleshooting

| Symptom | Guidance |
|---|---|
| Banner shows missing keys | Fill `.env`; public data/news still work without exchange keys |
| GDELT empty / 429 | Slow polls; RSS continues; sentiment → neutral |
| Groq 429 / auth error | Falls back to FinBERT/neutral; check key & rpm |
| Exchange auth fail | Use **Demo Trading** keys with `BYBIT_DEMO=true` / `enable_demo_trading` (not mainnet keys) |
| `api.api-demo.bybit.com` errors | Remove `hostname: api-demo.bybit.com`; use freqtrade `demo_trading: true` |
| Want exchange demo orders | Set `TRADING_MODE=demo` (not `paper`); keep live lock off |
| Clock drift warning | Enable NTP |
| Insufficient balance | Top up demo wallet / lower stakes / check dry_run_wallet |
| Kill switch engaged | Fix drawdown/daily loss; ack `RESET_KILL_SWITCH` on Risk page |
| Validation “insufficient bars” | `make download-data` with higher limit |
| Partial fills | Freqtrade will retry per unfilledtimeout; check open orders |
| Market closed / delisted | Remove pair from whitelist |
