# Skill: Add a strategy

1. Implement signal helpers in `src/crypto_bot/strategies/` (pure functions, tested).
2. Add a freqtrade `IStrategy` under `user_data/strategies/`.
3. Wire config defaults in `config/settings.yaml` + `Settings.to_freqtrade_config()`.
4. Ensure sentiment/risk remain filters/gates — strategy must not bypass `RiskManager`.
5. Document in `docs/strategies/` with evidence links and limitations.
6. Add unit tests for signals; run `make validate` on public data.
7. Run freqtrade `lookahead-analysis` and `recursive-analysis` before promoting.
