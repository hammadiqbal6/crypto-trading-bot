# Skill: Add an LLM provider

1. Subclass `LLMSentimentProvider` in `src/crypto_bot/sentiment/providers.py`.
2. Always anonymise via `anonymize()` before sending text.
3. Enforce `RateLimiter`; map failures to `SentimentError` with guidance.
4. Wire into `SentimentPipeline.from_settings` + enum in settings.
5. Update `.env.example`, README account table, and a unit test with httpx mock.
6. Ensure fallback chain still ends at FinBERT/neutral.
