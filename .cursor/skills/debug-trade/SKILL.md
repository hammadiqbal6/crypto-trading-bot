# Skill: Debug a failing trade

1. Check Risk panel / kill switch / daily loss / max open trades.
2. Read `user_data/logs/` and dashboard Logs page.
3. Verify exchange health (auth, clock drift, balance, downtime guidance).
4. Confirm sentiment feature file `user_data/sentiment_features.json` — blocked entries show reasons.
5. Inspect freqtrade trade DB / open orders; handle partial fills / insufficient balance messages.
6. Reproduce with dry_run; never escalate to live while debugging.
