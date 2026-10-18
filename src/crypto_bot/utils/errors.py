"""Domain errors with actionable user guidance."""

from __future__ import annotations


class CryptoBotError(Exception):
    """Base error with optional UI/log guidance."""

    def __init__(self, message: str, *, guidance: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.guidance = guidance or message

    def to_dict(self) -> dict[str, str]:
        return {"error": self.message, "guidance": self.guidance}


class ConfigError(CryptoBotError):
    pass


class ExchangeError(CryptoBotError):
    pass


class InsufficientBalanceError(ExchangeError):
    def __init__(self, message: str = "Insufficient balance for order") -> None:
        super().__init__(
            message,
            guidance=(
                "Check dry_run_wallet / demo balance. Reduce stake size or deposit "
                "demo funds. Partial fills may leave leftover dust — check open orders."
            ),
        )


class RateLimitError(CryptoBotError):
    def __init__(self, service: str, retry_after_s: float | None = None) -> None:
        ra = f" Retry after ~{retry_after_s:.0f}s." if retry_after_s else ""
        super().__init__(
            f"Rate limited by {service}.{ra}",
            guidance=(
                f"{service} rate limit hit.{ra} The bot backs off automatically. "
                "Lower NEWS/LLM poll frequency or upgrade the free tier if persistent."
            ),
        )


class NewsSourceError(CryptoBotError):
    pass


class SentimentError(CryptoBotError):
    pass


class RiskBreachError(CryptoBotError):
    """Hard risk rule violated — LLM/strategy cannot override."""

    def __init__(self, rule: str, detail: str) -> None:
        super().__init__(
            f"Risk breach ({rule}): {detail}",
            guidance=(
                f"Hard risk rule '{rule}' blocked the action. "
                "LLM sentiment never overrides risk. Review Risk panel / lower exposure."
            ),
        )


class ValidationError(CryptoBotError):
    pass


class MarketClosedError(ExchangeError):
    def __init__(self, pair: str) -> None:
        super().__init__(
            f"Market unavailable for {pair}",
            guidance=(
                f"{pair} appears halted or delisted on the exchange. "
                "Remove from pair_whitelist or wait for exchange recovery."
            ),
        )


class ClockDriftError(CryptoBotError):
    def __init__(self, drift_ms: float) -> None:
        super().__init__(
            f"Clock drift detected: {drift_ms:.0f}ms",
            guidance=(
                "System clock differs from exchange time. Sync NTP "
                "(sudo timedatectl set-ntp true) before trading."
            ),
        )
