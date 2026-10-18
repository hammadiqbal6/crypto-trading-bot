"""Sentiment pipeline: cache → LLM (optional) → FinBERT → neutral fallback."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from diskcache import Cache

from crypto_bot.news.service import NewsArticle
from crypto_bot.sentiment.providers import (
    FinBERTProvider,
    GroqProvider,
    OllamaProvider,
    OpenAIProvider,
    ProviderResult,
    SentimentProvider,
)
from crypto_bot.utils.errors import SentimentError
from crypto_bot.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class SentimentResult:
    score: float
    label: str
    provider: str
    cached: bool = False
    fallback: bool = False
    guidance: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "label": self.label,
            "provider": self.provider,
            "cached": self.cached,
            "fallback": self.fallback,
            "guidance": self.guidance,
        }


class SentimentPipeline:
    def __init__(
        self,
        primary: SentimentProvider | None,
        fallback: SentimentProvider | None = None,
        *,
        cache_dir: Path | None = None,
        cache_ttl_hours: int = 24,
    ) -> None:
        self.primary = primary
        self.fallback = fallback or FinBERTProvider()
        cache_path = cache_dir or Path("user_data") / "sentiment_cache"
        cache_path.mkdir(parents=True, exist_ok=True)
        self._cache = Cache(str(cache_path))
        self._ttl = cache_ttl_hours * 3600
        self.stats = {"hits": 0, "misses": 0, "fallback": 0, "errors": 0}

    @classmethod
    def from_settings(cls, settings: Any) -> SentimentPipeline:
        """Build pipeline: FinBERT local baseline, optional LLM, fallback chain.

        Order of attempts:
        1. FinBERT (local, no key) when use_finbert=True — research default
        2. Optional LLM (Groq/Ollama/OpenAI) if FinBERT fails or is disabled
        3. Neutral 0.0 if all providers fail

        When LLM is preferred for enrichment, set use_finbert=false and configure
        LLM_PROVIDER; on LLM failure we still try FinBERT if the model loads.
        """
        llm: SentimentProvider | None = None
        provider = str(getattr(settings, "llm_provider", "none")).lower()
        rpm = float(getattr(settings, "llm_rate_limit_rpm", 25))
        if provider == "groq":
            llm = GroqProvider(api_key=settings.groq_api_key.get_secret_value(), rpm=rpm)
        elif provider == "ollama":
            llm = OllamaProvider(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                rpm=rpm,
            )
        elif provider == "openai":
            llm = OpenAIProvider(
                api_key=settings.openai_api_key.get_secret_value(),
                model=settings.openai_model,
                rpm=rpm,
            )
        finbert = (
            FinBERTProvider(model_name=settings.finbert_model) if settings.use_finbert else None
        )
        # Research: FinBERT first, then LLM. On LLM failure → FinBERT/neutral.
        if finbert is not None:
            return cls(
                primary=finbert,
                fallback=llm,
                cache_ttl_hours=settings.sentiment_cache_ttl_hours,
            )
        return cls(
            primary=llm,
            fallback=FinBERTProvider(model_name=settings.finbert_model),
            cache_ttl_hours=settings.sentiment_cache_ttl_hours,
        )

    def _key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def score_text(self, text: str) -> SentimentResult:
        if not text.strip():
            return SentimentResult(0.0, "neutral", "empty", fallback=True)

        key = self._key(text.strip().lower())
        cached = self._cache.get(key)
        if cached is not None:
            self.stats["hits"] += 1
            return SentimentResult(
                score=float(cached["score"]),
                label=str(cached["label"]),
                provider=str(cached["provider"]),
                cached=True,
            )
        self.stats["misses"] += 1

        # Order: FinBERT first (when configured as primary), then LLM fallback enrichment.
        # If from_settings put FinBERT as primary and LLM as fallback, try primary then
        # optionally refine with LLM only when primary is uncertain — keep simple: primary → fallback → neutral
        result = await self._try_providers(text)
        self._cache.set(
            key,
            {"score": result.score, "label": result.label, "provider": result.provider},
            expire=self._ttl,
        )
        return result

    async def _try_providers(self, text: str) -> SentimentResult:
        errors: list[str] = []
        for provider in (self.primary, self.fallback):
            if provider is None:
                continue
            try:
                pr: ProviderResult = await provider.score(text)
                return SentimentResult(score=pr.score, label=pr.label, provider=pr.provider)
            except SentimentError as e:
                self.stats["errors"] += 1
                errors.append(e.guidance)
                log.warning(
                    "sentiment_provider_failed", provider=provider.name, guidance=e.guidance
                )
            except Exception as e:
                self.stats["errors"] += 1
                errors.append(str(e))
                log.warning("sentiment_provider_crash", provider=provider.name, error=str(e))

        self.stats["fallback"] += 1
        guidance = (
            "; ".join(errors) if errors else "No sentiment providers available — using neutral 0.0."
        )
        log.info("sentiment_neutral_fallback", guidance=guidance)
        return SentimentResult(
            score=0.0,
            label="neutral",
            provider="neutral_fallback",
            fallback=True,
            guidance=guidance,
        )

    async def enrich_articles(
        self, articles: list[NewsArticle], *, limit: int = 40
    ) -> list[NewsArticle]:
        for art in articles[:limit]:
            if art.sentiment_score is not None:
                continue
            res = await self.score_text(f"{art.title}. {art.summary}".strip())
            art.sentiment_score = res.score
            art.sentiment_label = res.label
            art.sentiment_provider = res.provider
        return articles
