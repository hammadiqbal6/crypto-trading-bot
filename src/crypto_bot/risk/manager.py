"""Hard risk rules: position limits, daily loss, drawdown kill switch, vol targeting.

LLM sentiment and strategy signals NEVER override these gates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from crypto_bot.utils.errors import RiskBreachError
from crypto_bot.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class RiskState:
    killed: bool = False
    kill_reason: str | None = None
    daily_pnl_pct: float = 0.0
    drawdown_pct: float = 0.0
    peak_equity: float = 0.0
    equity: float = 0.0
    open_trades: int = 0
    day: date = field(default_factory=lambda: datetime.now(UTC).date())
    blocked_entries: int = 0
    last_block_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "killed": self.killed,
            "kill_reason": self.kill_reason,
            "daily_pnl_pct": round(self.daily_pnl_pct, 4),
            "drawdown_pct": round(self.drawdown_pct, 4),
            "peak_equity": round(self.peak_equity, 2),
            "equity": round(self.equity, 2),
            "open_trades": self.open_trades,
            "day": self.day.isoformat(),
            "blocked_entries": self.blocked_entries,
            "last_block_reason": self.last_block_reason,
        }


class RiskManager:
    """Enforces non-negotiable risk constraints."""

    def __init__(
        self,
        *,
        max_open_trades: int = 3,
        max_daily_loss_pct: float = 3.0,
        max_drawdown_pct: float = 15.0,
        position_size_cap_pct: float = 0.25,
        volatility_target_annual: float = 0.20,
        stoploss_pct: float = -0.05,
        starting_equity: float = 10_000.0,
    ) -> None:
        self.max_open_trades = max_open_trades
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.position_size_cap_pct = position_size_cap_pct
        self.volatility_target_annual = volatility_target_annual
        self.stoploss_pct = stoploss_pct
        self.state = RiskState(equity=starting_equity, peak_equity=starting_equity)

    def update_equity(self, equity: float, *, realized_day_pnl_pct: float | None = None) -> None:
        today = datetime.now(UTC).date()
        if today != self.state.day:
            self.state.day = today
            self.state.daily_pnl_pct = 0.0
            # Kill switch does not auto-reset; operator must clear
        self.state.equity = equity
        if equity > self.state.peak_equity:
            self.state.peak_equity = equity
        if self.state.peak_equity > 0:
            self.state.drawdown_pct = (
                (self.state.peak_equity - equity) / self.state.peak_equity * 100.0
            )
        if realized_day_pnl_pct is not None:
            self.state.daily_pnl_pct = realized_day_pnl_pct
        self._check_kill_switch()

    def set_open_trades(self, n: int) -> None:
        self.state.open_trades = n

    def clear_kill_switch(self, *, operator_ack: str) -> None:
        if operator_ack != "RESET_KILL_SWITCH":
            raise RiskBreachError(
                "kill_switch_reset",
                "Provide operator_ack=RESET_KILL_SWITCH to clear the kill switch.",
            )
        self.state.killed = False
        self.state.kill_reason = None
        log.warning("kill_switch_cleared", by="operator")

    def _check_kill_switch(self) -> None:
        if self.state.drawdown_pct >= self.max_drawdown_pct:
            self._kill(f"max drawdown {self.state.drawdown_pct:.2f}% >= {self.max_drawdown_pct}%")
        if self.state.daily_pnl_pct <= -abs(self.max_daily_loss_pct):
            self._kill(f"daily loss {self.state.daily_pnl_pct:.2f}% <= -{self.max_daily_loss_pct}%")

    def _kill(self, reason: str) -> None:
        if not self.state.killed:
            log.error("kill_switch_engaged", reason=reason)
        self.state.killed = True
        self.state.kill_reason = reason

    def _block(self, reason: str) -> None:
        self.state.blocked_entries += 1
        self.state.last_block_reason = reason
        log.info("entry_blocked", reason=reason)

    def assert_can_enter(self, *, proposed_size_pct: float | None = None) -> None:
        """Raise RiskBreachError if a new entry must be blocked."""
        if self.state.killed:
            self._block(self.state.kill_reason or "killed")
            raise RiskBreachError("kill_switch", self.state.kill_reason or "bot killed")
        if self.state.open_trades >= self.max_open_trades:
            reason = f"max open trades {self.state.open_trades}/{self.max_open_trades}"
            self._block(reason)
            raise RiskBreachError("max_open_trades", reason)
        if proposed_size_pct is not None and proposed_size_pct > self.position_size_cap_pct:
            reason = f"size {proposed_size_pct:.2%} exceeds cap {self.position_size_cap_pct:.2%}"
            self._block(reason)
            raise RiskBreachError("position_size_cap", reason)

    def volatility_scale(self, realized_vol_annual: float) -> float:
        """Moreira & Muir style vol targeting; capped to position_size_cap."""
        if realized_vol_annual <= 1e-8:
            return 0.0
        raw = self.volatility_target_annual / realized_vol_annual
        return float(min(max(raw, 0.0), self.position_size_cap_pct / 0.1, 2.0))

    def apply_sentiment_size(
        self,
        base_size: float,
        sentiment_score: float,
        *,
        block_threshold: float,
        sizeup_threshold: float,
        sizeup_factor: float,
    ) -> tuple[float, str]:
        """
        News filter: block on strongly negative; small size-up on positive.
        Returns (adjusted_size, reason). Never bypasses hard risk — caller must
        still call assert_can_enter.
        """
        if sentiment_score <= block_threshold:
            return 0.0, f"blocked by negative sentiment ({sentiment_score:.2f})"
        if sentiment_score >= sizeup_threshold:
            sized = min(base_size * sizeup_factor, self.position_size_cap_pct)
            return sized, f"size-up on positive sentiment ({sentiment_score:.2f})"
        return base_size, "sentiment neutral — base size"
