"""Sentiment pipeline with mocked providers."""

from __future__ import annotations

import pytest

from crypto_bot.sentiment.pipeline import SentimentPipeline
from crypto_bot.sentiment.providers import ProviderResult, SentimentProvider
from crypto_bot.utils.errors import SentimentError


class OKProvider(SentimentProvider):
    name = "ok"

    async def score(self, text: str) -> ProviderResult:
        return ProviderResult(score=0.6, label="positive", provider=self.name)


class FailProvider(SentimentProvider):
    name = "fail"

    async def score(self, text: str) -> ProviderResult:
        raise SentimentError("boom", guidance="fallback please")


@pytest.mark.asyncio
async def test_cache_hit(tmp_path) -> None:  # type: ignore[no-untyped-def]
    pipe = SentimentPipeline(OKProvider(), cache_dir=tmp_path, cache_ttl_hours=1)
    a = await pipe.score_text("markets rise")
    b = await pipe.score_text("markets rise")
    assert a.score == 0.6
    assert b.cached is True
    assert pipe.stats["hits"] == 1


@pytest.mark.asyncio
async def test_fallback_to_neutral(tmp_path) -> None:  # type: ignore[no-untyped-def]
    pipe = SentimentPipeline(FailProvider(), fallback=None, cache_dir=tmp_path)
    res = await pipe.score_text("chaos")
    assert res.provider == "neutral_fallback"
    assert res.score == 0.0
    assert res.fallback is True


@pytest.mark.asyncio
async def test_fallback_provider(tmp_path) -> None:  # type: ignore[no-untyped-def]
    pipe = SentimentPipeline(FailProvider(), fallback=OKProvider(), cache_dir=tmp_path)
    res = await pipe.score_text("chaos")
    assert res.provider == "ok"
    assert res.score == 0.6
