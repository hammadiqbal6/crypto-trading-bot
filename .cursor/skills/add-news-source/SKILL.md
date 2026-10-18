# Skill: Add a news source

1. Implement a `NewsSource` subclass in `src/crypto_bot/news/sources.py`.
2. Rate-limit and map errors to `NewsSourceError` / `RateLimitError` with guidance.
3. Register in `NewsService.from_settings` behind a config flag.
4. Document env vars in `.env.example` + README account table (required/optional, Pakistan note).
5. Unit-test parsing with fixtures; never require live network in unit tests.
