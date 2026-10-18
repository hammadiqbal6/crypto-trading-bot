"""News service: aggregate sources, dedupe, attach coin tags."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from crypto_bot.news.sources import GDELTSource, NewsSource, RawArticle, RedditSource, RSSSource
from crypto_bot.utils.errors import NewsSourceError, RateLimitError
from crypto_bot.utils.logging import get_logger

log = get_logger(__name__)

COIN_ALIASES: dict[str, tuple[str, ...]] = {
    "BTC": ("bitcoin", "btc", "xbt"),
    "ETH": ("ethereum", "eth", "ether"),
    "SOL": ("solana", "sol"),
    "BNB": ("binance coin", "bnb", "bnb chain"),
    "XRP": ("xrp", "ripple"),
    "ADA": ("cardano", "ada"),
    "AVAX": ("avalanche", "avax"),
    "DOGE": ("dogecoin", "doge"),
    "LINK": ("chainlink", "link"),
    "DOT": ("polkadot", "dot"),
}


@dataclass
class NewsArticle:
    source: str
    title: str
    url: str
    published: datetime | None
    summary: str = ""
    coins: list[str] = field(default_factory=list)
    sentiment_score: float | None = None
    sentiment_label: str | None = None
    sentiment_provider: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "title": self.title,
            "url": self.url,
            "published": self.published.isoformat() if self.published else None,
            "summary": self.summary,
            "coins": self.coins,
            "sentiment_score": self.sentiment_score,
            "sentiment_label": self.sentiment_label,
            "sentiment_provider": self.sentiment_provider,
        }


def detect_coins(text: str) -> list[str]:
    lower = text.lower()
    found: list[str] = []
    for coin, aliases in COIN_ALIASES.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", lower):
                found.append(coin)
                break
    return found


def pair_to_coin(pair: str) -> str:
    return pair.split("/")[0].upper().replace("USDT", "").replace("USD", "") or pair


class NewsService:
    def __init__(self, sources: list[NewsSource] | None = None) -> None:
        self.sources = sources or [GDELTSource(), RSSSource()]
        self._cache: list[NewsArticle] = []
        self._cache_at: datetime | None = None
        self.last_errors: list[dict[str, str]] = []

    @classmethod
    def from_settings(cls, settings: Any) -> NewsService:
        sources: list[NewsSource] = [GDELTSource(), RSSSource()]
        if getattr(settings, "news_enable_reddit", False):
            sources.append(
                RedditSource(
                    client_id=settings.reddit_client_id.get_secret_value(),
                    client_secret=settings.reddit_client_secret.get_secret_value(),
                    user_agent=settings.reddit_user_agent,
                )
            )
        return cls(sources=sources)

    async def fetch_for_universe(
        self,
        pairs: list[str],
        *,
        max_age_hours: int = 48,
        max_per_source: int = 20,
        force: bool = False,
    ) -> list[NewsArticle]:
        now = datetime.now(UTC)
        if (
            not force
            and self._cache_at
            and (now - self._cache_at) < timedelta(minutes=10)
            and self._cache
        ):
            return self._cache

        coins = sorted({pair_to_coin(p) for p in pairs})
        query = " OR ".join(coins[:6])
        raw: list[RawArticle] = []
        self.last_errors = []
        for src in self.sources:
            try:
                batch = await src.fetch(query, max_items=max_per_source)
                raw.extend(batch)
                log.info("news_source_ok", source=src.name, count=len(batch))
            except RateLimitError as e:
                self.last_errors.append(e.to_dict())
                log.warning("news_rate_limited", source=src.name, guidance=e.guidance)
            except NewsSourceError as e:
                self.last_errors.append(e.to_dict())
                log.warning("news_source_error", source=src.name, guidance=e.guidance)
            except Exception as e:
                err = NewsSourceError(
                    str(e),
                    guidance=f"Unexpected error from {src.name}. Other sources continue.",
                )
                self.last_errors.append(err.to_dict())
                log.exception("news_source_crash", source=src.name)

        # Dedupe by URL / title
        seen: set[str] = set()
        articles: list[NewsArticle] = []
        cutoff = now - timedelta(hours=max_age_hours)
        for r in raw:
            key = (r.url or r.title).lower()
            if key in seen:
                continue
            seen.add(key)
            if r.published and r.published < cutoff:
                continue
            coins_hit = detect_coins(f"{r.title} {r.summary}")
            articles.append(
                NewsArticle(
                    source=r.source,
                    title=r.title,
                    url=r.url,
                    published=r.published,
                    summary=r.summary,
                    coins=coins_hit,
                )
            )
        articles.sort(key=lambda a: a.published or datetime.min.replace(tzinfo=UTC), reverse=True)
        self._cache = articles
        self._cache_at = now
        if not articles:
            log.warning(
                "news_empty",
                guidance=(
                    "No recent news articles. Check network, GDELT availability, or RSS feeds. "
                    "Strategy will treat sentiment as neutral."
                ),
            )
        return articles

    async def score_for_pair(self, pair: str, articles: list[NewsArticle] | None = None) -> float:
        """Average sentiment for a pair; 0.0 = neutral if none."""
        coin = pair_to_coin(pair)
        arts = articles if articles is not None else self._cache
        scores = [
            a.sentiment_score
            for a in arts
            if a.sentiment_score is not None and (coin in a.coins or not a.coins)
        ]
        if not scores:
            return 0.0
        # Prefer coin-tagged
        tagged = [
            a.sentiment_score for a in arts if a.sentiment_score is not None and coin in a.coins
        ]
        use = tagged if tagged else scores
        return float(sum(use) / len(use))
