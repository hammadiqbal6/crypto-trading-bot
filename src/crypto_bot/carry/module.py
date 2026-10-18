"""Delta-neutral funding/basis carry — optional, off by default.

Evidence: BIS WP 1087 — BTC/ETH basis ~7%/yr 2019-2024; liquidation/exchange risk.
Requires derivatives (Bybit). Never enabled unless CARRY_ENABLED=true.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from crypto_bot.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class CarryOpportunity:
    symbol: str
    funding_rate: float
    basis_apr: float
    annualized_edge: float
    actionable: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "funding_rate": self.funding_rate,
            "basis_apr": self.basis_apr,
            "annualized_edge": self.annualized_edge,
            "actionable": self.actionable,
            "reason": self.reason,
        }


class CarryModule:
    """
    Scans funding / basis for delta-neutral carry candidates.
    Does NOT place trades unless explicitly enabled and called by operator tools.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        min_funding_apr: float = 0.08,
        margin_buffer_pct: float = 0.30,
    ) -> None:
        self.enabled = enabled
        self.min_funding_apr = min_funding_apr
        self.margin_buffer_pct = margin_buffer_pct

    def evaluate(
        self,
        symbol: str,
        funding_rate_8h: float,
        spot: float,
        perp: float,
    ) -> CarryOpportunity:
        if not self.enabled:
            return CarryOpportunity(
                symbol=symbol,
                funding_rate=funding_rate_8h,
                basis_apr=0.0,
                annualized_edge=0.0,
                actionable=False,
                reason="Carry module disabled (CARRY_ENABLED=false). Safe default.",
            )
        if spot <= 0 or perp <= 0:
            return CarryOpportunity(
                symbol=symbol,
                funding_rate=funding_rate_8h,
                basis_apr=0.0,
                annualized_edge=0.0,
                actionable=False,
                reason="Invalid spot/perp prices — check market data feed.",
            )
        # 3 funding periods/day * 365
        funding_apr = funding_rate_8h * 3 * 365
        basis = (perp - spot) / spot
        basis_apr = basis * 365  # rough 1-day roll annualisation; demo heuristic
        edge = funding_apr + max(basis_apr, 0.0) * 0.0  # prefer funding for demo
        # For positive funding, short perp + long spot is classic cash-and-carry
        actionable = funding_apr >= self.min_funding_apr
        reason = (
            f"funding_apr={funding_apr:.2%} basis_apr={basis_apr:.2%} "
            f"buffer={self.margin_buffer_pct:.0%}"
        )
        if actionable:
            reason += " | candidate (operator must confirm; auto-trade off)"
        else:
            reason += " | below min funding threshold"
        log.info("carry_eval", symbol=symbol, actionable=actionable, edge=edge)
        return CarryOpportunity(
            symbol=symbol,
            funding_rate=funding_rate_8h,
            basis_apr=basis_apr,
            annualized_edge=funding_apr,
            actionable=actionable,
            reason=reason,
        )
