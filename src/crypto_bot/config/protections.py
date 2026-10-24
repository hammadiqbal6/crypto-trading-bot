"""Map Signalforge risk limits to freqtrade protection configs."""

from __future__ import annotations

from typing import Any


def build_freqtrade_protections(
    *,
    max_drawdown_pct: float,
    max_daily_loss_pct: float,
    timeframe: str = "4h",
) -> list[dict[str, Any]]:
    """Build freqtrade ``protections`` entries from risk settings.

    - MaxDrawdown (equity, long lookback) ≈ ``MAX_DRAWDOWN_PCT`` kill switch
    - MaxDrawdown (equity, 1-day lookback) ≈ ``MAX_DAILY_LOSS_PCT``
    - StoplossGuard slows re-entry after repeated stops

    Values are fractions (15% → 0.15). Used by the strategy and exported config.
    """
    max_dd = abs(float(max_drawdown_pct)) / 100.0
    max_daily = abs(float(max_daily_loss_pct)) / 100.0
    # Long lock after portfolio drawdown breach (near kill-switch behaviour).
    # 10_000 candles on 4h ≈ years — effectively stops new entries for the run.
    return [
        {
            "method": "MaxDrawdown",
            "lookback_period_candles": 10_000,
            "trade_limit": 1,
            "stop_duration_candles": 10_000,
            "max_allowed_drawdown": max_dd,
            "calculation_mode": "equity",
        },
        {
            "method": "MaxDrawdown",
            "lookback_period": 1440,  # rolling 24h window (minutes)
            "trade_limit": 1,
            "unlock_at": "00:00",
            "max_allowed_drawdown": max_daily,
            "calculation_mode": "equity",
        },
        {
            "method": "StoplossGuard",
            "lookback_period_candles": 48 if timeframe.endswith("h") else 24,
            "trade_limit": 4,
            "stop_duration_candles": 12,
            "required_profit": 0.0,
        },
    ]
