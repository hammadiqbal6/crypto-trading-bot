"""Pluggable news sources — GDELT (no key), RSS (no key), optional Reddit."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote_plus

import feedparser
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from crypto_bot.utils.errors import NewsSourceError, RateLimitError
from crypto_bot.utils.logging import get_logger
from crypto_bot.utils.rate_limit import RateLimiter

log = get_logger(__name__)

CRYPTO_RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://www.theblock.co/rss.xml",
    "https://decrypt.co/feed",
]

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"


@dataclass(frozen=True)
class RawArticle:
    source: str
    title: str
    url: str
    published: datetime | None
    summary: str = ""
    entities: tuple[str, ...] = ()


class NewsSource(ABC):
    name: str

    @abstractmethod
    async def fetch(self, query: str, *, max_items: int = 25) -> list[RawArticle]:
        raise NotImplementedError


class GDELTSource(NewsSource):
    """GDELT DOC 2.0 — free, no API key. ~1 req / 5s recommended."""

    name = "gdelt"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._limiter = RateLimiter(rate_per_minute=10)  # ~1/6s

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
    async def fetch(self, query: str, *, max_items: int = 25) -> list[RawArticle]:
        await self._limiter.acquire()
        # Prefer crypto-related query; GDELT uses free text
        q = f"({query}) (bitcoin OR crypto OR cryptocurrency OR ethereum)"
        params = {
            "query": q,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": str(min(max_items, 50)),
            "sort": "DateDesc",
        }
        client = await self._http()
        try:
            resp = await client.get(GDELT_DOC_API, params=params)
        except httpx.HTTPError as e:
            raise NewsSourceError(
                f"GDELT network error: {e}",
                guidance=(
                    "GDELT DOC API unreachable. Check network/DNS. "
                    "RSS feeds still work without GDELT. Retry later."
                ),
            ) from e
        if resp.status_code == 429:
            raise RateLimitError("GDELT", retry_after_s=30)
        if resp.status_code >= 400:
            raise NewsSourceError(
                f"GDELT HTTP {resp.status_code}",
                guidance="GDELT returned an error. Slow requests to ~1/5s. RSS remains available.",
            )
        try:
            payload = resp.json()
        except Exception as e:
            # GDELT occasionally returns plain text / empty
            log.warning("gdelt_bad_json", error=str(e))
            return []
        articles: list[RawArticle] = []
        for item in payload.get("articles", []) or []:
            title = (item.get("title") or "").strip()
            url = (item.get("url") or "").strip()
            if not title or not url:
                continue
            seendate = item.get("seendate")
            published = None
            if seendate:
                try:
                    published = datetime.strptime(seendate, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
                except ValueError:
                    published = None
            articles.append(
                RawArticle(
                    source="gdelt",
                    title=title,
                    url=url,
                    published=published,
                    summary=(item.get("seendate") or ""),
                )
            )
        return articles


class RSSSource(NewsSource):
    """Crypto RSS feeds — no API key required."""

    name = "rss"

    def __init__(
        self,
        feeds: list[str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.feeds = feeds or CRYPTO_RSS_FEEDS
        self._client = client

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        return self._client

    async def fetch(self, query: str, *, max_items: int = 25) -> list[RawArticle]:
        client = await self._http()
        keywords = [k.lower() for k in query.replace("/", " ").split() if len(k) > 1]
        articles: list[RawArticle] = []

        async def one(url: str) -> list[RawArticle]:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                log.warning("rss_fetch_failed", url=url, error=str(e))
                return []
            parsed = feedparser.parse(resp.text)
            out: list[RawArticle] = []
            for entry in parsed.entries:
                title = (getattr(entry, "title", None) or "").strip()
                link = (getattr(entry, "link", None) or "").strip()
                summary = (getattr(entry, "summary", None) or "")[:500]
                if not title:
                    continue
                blob = f"{title} {summary}".lower()
                if keywords and not any(k.lower() in blob for k in keywords):
                    # Keep some general crypto headlines even without coin match
                    if not any(w in blob for w in ("bitcoin", "crypto", "ethereum", "btc", "eth")):
                        continue
                published = None
                if getattr(entry, "published_parsed", None):
                    try:
                        published = datetime(*entry.published_parsed[:6], tzinfo=UTC)  # type: ignore[misc]
                    except Exception:
                        published = None
                out.append(
                    RawArticle(
                        source=f"rss:{parsed.feed.get('title', url)}",
                        title=title,
                        url=link or url,
                        published=published,
                        summary=summary,
                    )
                )
            return out

        results = await asyncio.gather(*(one(u) for u in self.feeds))
        for batch in results:
            articles.extend(batch)
        # Prefer query matches first
        articles.sort(
            key=lambda a: (
                0 if any(k in a.title.lower() for k in keywords) else 1,
                -(a.published.timestamp() if a.published else 0),
            )
        )
        return articles[:max_items]


class RedditSource(NewsSource):
    """Optional Reddit source — requires free app credentials."""

    name = "reddit"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self._client = client
        self._token: str | None = None
        self._limiter = RateLimiter(rate_per_minute=60)

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _auth(self) -> str:
        if self._token:
            return self._token
        if not self.client_id or not self.client_secret:
            raise NewsSourceError(
                "Reddit credentials missing",
                guidance=(
                    "Set REDDIT_CLIENT_ID/SECRET or disable NEWS_ENABLE_REDDIT. "
                    "GDELT + RSS need no keys."
                ),
            )
        client = await self._http()
        resp = await client.post(
            "https://www.reddit.com/api/v1/access_token",
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            headers={"User-Agent": self.user_agent},
        )
        if resp.status_code >= 400:
            raise NewsSourceError(
                f"Reddit auth failed: HTTP {resp.status_code}",
                guidance="Check Reddit app credentials at https://www.reddit.com/prefs/apps",
            )
        self._token = resp.json()["access_token"]
        return self._token

    async def fetch(self, query: str, *, max_items: int = 25) -> list[RawArticle]:
        await self._limiter.acquire()
        token = await self._auth()
        client = await self._http()
        q = quote_plus(query)
        resp = await client.get(
            f"https://oauth.reddit.com/r/CryptoCurrency/search",
            params={"q": q, "restrict_sr": "true", "sort": "new", "limit": str(max_items)},
            headers={"Authorization": f"Bearer {token}", "User-Agent": self.user_agent},
        )
        if resp.status_code == 429:
            raise RateLimitError("Reddit", retry_after_s=60)
        if resp.status_code >= 400:
            raise NewsSourceError(
                f"Reddit HTTP {resp.status_code}",
                guidance="Reddit API error. Disable NEWS_ENABLE_REDDIT if access closed.",
            )
        data: dict[str, Any] = resp.json()
        articles: list[RawArticle] = []
        for child in (data.get("data") or {}).get("children") or []:
            d = child.get("data") or {}
            title = (d.get("title") or "").strip()
            if not title:
                continue
            created = d.get("created_utc")
            published = datetime.fromtimestamp(created, tz=UTC) if created else None
            articles.append(
                RawArticle(
                    source="reddit",
                    title=title,
                    url="https://reddit.com" + str(d.get("permalink") or ""),
                    published=published,
                    summary=(d.get("selftext") or "")[:500],
                )
            )
        return articles
