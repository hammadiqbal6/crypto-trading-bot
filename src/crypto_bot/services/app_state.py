"""In-process app state shared by API/dashboard and background jobs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from crypto_bot.carry.module import CarryModule
from crypto_bot.config.settings import Settings, get_settings
from crypto_bot.exchanges.health import ExchangeHealth, check_exchange_health
from crypto_bot.news.service import NewsArticle, NewsService
from crypto_bot.risk.manager import RiskManager, RiskState
from crypto_bot.sentiment.pipeline import SentimentPipeline
from crypto_bot.utils.logging import get_logger
from crypto_bot.validation.walk_forward import WalkForwardResult

log = get_logger(__name__)


@dataclass
class SignalSnapshot:
    pair: str
    action: str
    reason: str
    sentiment: float
    score: float
    ts: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class AppState:
    settings: Settings
    risk: RiskManager
    news: NewsService
    sentiment: SentimentPipeline
    carry: CarryModule
    exchange_health: ExchangeHealth | None = None
    articles: list[NewsArticle] = field(default_factory=list)
    signals: list[SignalSnapshot] = field(default_factory=list)
    validation: WalkForwardResult | None = None
    bot_running: bool = False
    last_refresh: str | None = None
    logs: list[str] = field(default_factory=list)
    onboarding_step: int = 0

    def add_log(self, msg: str) -> None:
        ts = datetime.now(UTC).isoformat()
        line = f"{ts} {msg}"
        self.logs.append(line)
        self.logs = self.logs[-500:]

    def risk_state(self) -> RiskState:
        return self.risk.state

    def status_dict(self) -> dict[str, Any]:
        s = self.settings
        return {
            "version": "0.1.0",
            "trading_mode": s.trading_mode.value,
            "live_trading": s.live_trading,
            "dry_run": s.is_dry_run,
            "exchange": s.exchange_name.value,
            "bybit_demo": s.bybit_demo,
            "bot_running": self.bot_running,
            "freqai_enabled": s.freqai_enabled,
            "carry_enabled": s.carry_enabled,
            "pairs": s.pair_whitelist,
            "timeframe": s.timeframe,
            "last_refresh": self.last_refresh,
            "guidance": s.missing_required_guidance(),
            "accuracy_disclaimer": (
                "No free method reliably beats ~51-55% daily directional accuracy "
                "out-of-sample. Target Sharpe after costs: 0.5-1.0."
            ),
        }

    def write_sentiment_features(self) -> Path:
        """Write pair→score JSON consumed by the freqtrade strategy."""
        path = self.settings.user_data_dir / "sentiment_features.json"
        scores: dict[str, float] = {}
        for pair in self.settings.pair_whitelist:
            # average from articles (already enriched)
            coin = pair.split("/")[0]
            tagged = [
                a.sentiment_score
                for a in self.articles
                if a.sentiment_score is not None and coin in a.coins
            ]
            if tagged:
                scores[pair] = float(sum(tagged) / len(tagged))
                scores[coin] = scores[pair]
            else:
                scores[pair] = 0.0
        payload = {
            "updated_at": datetime.now(UTC).isoformat(),
            "scores": scores,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    async def refresh_news_and_sentiment(self) -> list[NewsArticle]:
        self.add_log("Refreshing news…")
        articles = await self.news.fetch_for_universe(self.settings.pair_whitelist)
        articles = await self.sentiment.enrich_articles(articles)
        self.articles = articles
        self.write_sentiment_features()
        self.last_refresh = datetime.now(UTC).isoformat()
        self.add_log(f"News refresh done: {len(articles)} articles")
        # Build simple signal snapshots for UI
        block = self.settings.sentiment_block_threshold
        sizeup = self.settings.sentiment_sizeup_threshold
        snaps: list[SignalSnapshot] = []
        for pair in self.settings.pair_whitelist:
            coin = pair.split("/")[0]
            tagged = [
                a.sentiment_score
                for a in articles
                if a.sentiment_score is not None and coin in a.coins
            ]
            sent = float(sum(tagged) / len(tagged)) if tagged else 0.0
            if sent <= block:
                action, reason = "blocked", f"Negative sentiment {sent:.2f} ≤ {block}"
            elif sent >= sizeup:
                action, reason = "size-up", f"Positive sentiment {sent:.2f} ≥ {sizeup}"
            else:
                action, reason = "allow", f"Neutral sentiment {sent:.2f}"
            snaps.append(
                SignalSnapshot(
                    pair=pair,
                    action=action,
                    reason=reason,
                    sentiment=sent,
                    score=sent,
                    ts=self.last_refresh or "",
                )
            )
        self.signals = snaps
        return articles

    def refresh_exchange_health(self) -> ExchangeHealth:
        health = check_exchange_health(self.settings)
        self.exchange_health = health
        self.add_log(f"Exchange health: ok={health.ok} {health.message}")
        return health


_STATE: AppState | None = None


def get_app_state(*, reload: bool = False) -> AppState:
    global _STATE
    if _STATE is None or reload:
        settings = get_settings(reload=reload)
        _STATE = AppState(
            settings=settings,
            risk=RiskManager(
                max_open_trades=settings.max_open_trades,
                max_daily_loss_pct=settings.max_daily_loss_pct,
                max_drawdown_pct=settings.max_drawdown_pct,
                position_size_cap_pct=settings.position_size_cap_pct,
                volatility_target_annual=settings.volatility_target_annual,
                stoploss_pct=settings.stoploss_pct,
                starting_equity=settings.dry_run_wallet,
            ),
            news=NewsService.from_settings(settings),
            sentiment=SentimentPipeline.from_settings(settings),
            carry=CarryModule(enabled=settings.carry_enabled),
        )
    return _STATE
