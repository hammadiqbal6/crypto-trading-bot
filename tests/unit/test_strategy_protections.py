"""Strategy wires risk settings into freqtrade protections.

CI installs ``.[dev]`` without the optional ``engine`` extra (freqtrade).
Stub a minimal ``freqtrade.strategy`` when the package is absent so this unit
test still validates protection wiring without pulling the full engine.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _ensure_freqtrade_strategy_importable() -> None:
    try:
        import freqtrade.strategy  # noqa: F401

        return
    except ImportError:
        pass
    if "freqtrade.strategy" in sys.modules:
        return
    ft = types.ModuleType("freqtrade")
    strat = types.ModuleType("freqtrade.strategy")

    class IStrategy:
        def __init__(self, config: dict) -> None:
            self.config = config

    class IntParameter:
        def __init__(self, low: int, high: int, default: int = 0, **kwargs: object) -> None:
            self.value = default

    strat.IStrategy = IStrategy  # type: ignore[attr-defined]
    strat.IntParameter = IntParameter  # type: ignore[attr-defined]
    sys.modules["freqtrade"] = ft
    sys.modules["freqtrade.strategy"] = strat


def _load_strategy_class():
    _ensure_freqtrade_strategy_importable()
    path = (
        Path(__file__).resolve().parents[2] / "user_data/strategies/VolatilityMomentumStrategy.py"
    )
    spec = importlib.util.spec_from_file_location("vol_mom_strategy", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.VolatilityMomentumStrategy


def test_strategy_protections_from_crypto_bot_config() -> None:
    strategy_cls = _load_strategy_class()
    cfg = {
        "timeframe": "4h",
        "stake_currency": "USDT",
        "dry_run": True,
        "exchange": {"name": "bybit", "pair_whitelist": ["BTC/USDT"]},
        "crypto_bot": {
            "max_drawdown_pct": 12.0,
            "max_daily_loss_pct": 2.5,
            "sentiment_block_threshold": -0.55,
            "sentiment_sizeup_threshold": 0.45,
            "sentiment_sizeup_factor": 1.15,
            "volatility_target_annual": 0.2,
        },
    }
    strat = strategy_cls(cfg)
    assert isinstance(strat.protections, list)
    assert len(strat.protections) >= 3
    dd = next(
        p
        for p in strat.protections
        if p["method"] == "MaxDrawdown" and "lookback_period_candles" in p
    )
    assert dd["max_allowed_drawdown"] == 0.12
    daily = next(
        p
        for p in strat.protections
        if p["method"] == "MaxDrawdown" and p.get("lookback_period") == 1440
    )
    assert daily["max_allowed_drawdown"] == 0.025
    assert any(p["method"] == "StoplossGuard" for p in strat.protections)
