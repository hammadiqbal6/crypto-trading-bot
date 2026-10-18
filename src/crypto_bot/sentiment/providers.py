"""Pluggable sentiment providers: FinBERT (local), Groq, Ollama, OpenAI."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

from crypto_bot.sentiment.anonymize import anonymize
from crypto_bot.utils.errors import SentimentError
from crypto_bot.utils.logging import get_logger
from crypto_bot.utils.rate_limit import RateLimiter

log = get_logger(__name__)

SENTIMENT_PROMPT = """You are a financial news sentiment classifier.
Given an anonymised crypto headline, reply with ONLY JSON:
{"label":"positive"|"negative"|"neutral","score":<float from -1 to 1>}
Do not identify entities. Do not give trading advice.
Headline: {headline}
"""


@dataclass
class ProviderResult:
    score: float  # -1 .. 1
    label: str
    provider: str
    raw: str = ""


class SentimentProvider(ABC):
    name: str

    @abstractmethod
    async def score(self, text: str) -> ProviderResult:
        raise NotImplementedError


class FinBERTProvider(SentimentProvider):
    """Local FinBERT — no API key. Lazy-loads transformers model."""

    name = "finbert"

    def __init__(self, model_name: str = "ProsusAI/finbert") -> None:
        self.model_name = model_name
        self._pipe: Any | None = None
        self._failed = False

    def _load(self) -> Any | None:
        if self._failed:
            return None
        if self._pipe is not None:
            return self._pipe
        try:
            from transformers import pipeline

            self._pipe = pipeline(
                "sentiment-analysis",
                model=self.model_name,
                truncation=True,
            )
            return self._pipe
        except Exception as e:
            self._failed = True
            log.warning(
                "finbert_load_failed",
                error=str(e),
                guidance="FinBERT unavailable. Install torch+transformers or rely on LLM/neutral.",
            )
            return None

    async def score(self, text: str) -> ProviderResult:
        pipe = self._load()
        if pipe is None:
            raise SentimentError(
                "FinBERT unavailable",
                guidance="Install torch and transformers, or configure an LLM provider.",
            )
        # transformers is sync; run as-is (CPU). Keep text short.
        result = pipe(text[:512])[0]
        label = str(result.get("label", "neutral")).lower()
        conf = float(result.get("score", 0.0))
        if "pos" in label:
            score = conf
            label = "positive"
        elif "neg" in label:
            score = -conf
            label = "negative"
        else:
            score = 0.0
            label = "neutral"
        return ProviderResult(score=score, label=label, provider=self.name, raw=str(result))


class LLMSentimentProvider(SentimentProvider):
    """Base for chat-completion style LLMs with anonymisation."""

    name = "llm"

    def __init__(self, rate_per_minute: float = 25) -> None:
        self._limiter = RateLimiter(rate_per_minute=rate_per_minute)

    async def _complete(self, prompt: str) -> str:
        raise NotImplementedError

    async def score(self, text: str) -> ProviderResult:
        anon = anonymize(text)
        prompt = SENTIMENT_PROMPT.format(headline=anon.text)
        await self._limiter.acquire()
        try:
            raw = await self._complete(prompt)
        except Exception as e:
            raise SentimentError(
                f"{self.name} failed: {e}",
                guidance=(
                    f"LLM provider '{self.name}' failed. Falling back to FinBERT/neutral. "
                    "Check API key, rate limits, and network."
                ),
            ) from e
        return self._parse(raw)

    def _parse(self, raw: str) -> ProviderResult:
        score = 0.0
        label = "neutral"
        try:
            match = re.search(r"\{.*?\}", raw, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                label = str(data.get("label", "neutral")).lower()
                score = float(data.get("score", 0.0))
        except (json.JSONDecodeError, TypeError, ValueError):
            low = raw.lower()
            if "positive" in low:
                label, score = "positive", 0.4
            elif "negative" in low:
                label, score = "negative", -0.4
        score = max(-1.0, min(1.0, score))
        return ProviderResult(score=score, label=label, provider=self.name, raw=raw[:500])


class GroqProvider(LLMSentimentProvider):
    name = "groq"

    def __init__(self, api_key: str, model: str = "llama-3.1-8b-instant", rpm: float = 25) -> None:
        super().__init__(rate_per_minute=rpm)
        self.api_key = api_key
        self.model = model

    async def _complete(self, prompt: str) -> str:
        if not self.api_key:
            raise SentimentError(
                "GROQ_API_KEY missing",
                guidance="Set GROQ_API_KEY from https://console.groq.com or set LLM_PROVIDER=none.",
            )
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 80,
                },
            )
        if resp.status_code == 429:
            raise SentimentError(
                "Groq rate limited",
                guidance="Groq free tier ~30 rpm. Cache hits help; FinBERT fallback engages.",
            )
        if resp.status_code >= 400:
            raise SentimentError(
                f"Groq HTTP {resp.status_code}: {resp.text[:200]}",
                guidance="Check GROQ_API_KEY validity and model name.",
            )
        data = resp.json()
        return str(data["choices"][0]["message"]["content"])


class OllamaProvider(LLMSentimentProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, rpm: float = 30) -> None:
        super().__init__(rate_per_minute=rpm)
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def _complete(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
        if resp.status_code >= 400:
            raise SentimentError(
                f"Ollama HTTP {resp.status_code}",
                guidance=f"Is Ollama running at {self.base_url}? Try: ollama run {self.model}",
            )
        return str(resp.json().get("response", ""))


class OpenAIProvider(LLMSentimentProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", rpm: float = 20) -> None:
        super().__init__(rate_per_minute=rpm)
        self.api_key = api_key
        self.model = model

    async def _complete(self, prompt: str) -> str:
        if not self.api_key:
            raise SentimentError(
                "OPENAI_API_KEY missing",
                guidance="Set OPENAI_API_KEY or switch LLM_PROVIDER to groq/ollama/none.",
            )
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 80,
                },
            )
        if resp.status_code >= 400:
            raise SentimentError(
                f"OpenAI HTTP {resp.status_code}",
                guidance="Check OPENAI_API_KEY and billing status.",
            )
        return str(resp.json()["choices"][0]["message"]["content"])
