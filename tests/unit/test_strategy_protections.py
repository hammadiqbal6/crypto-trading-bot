"""Strategy wires risk settings into freqtrade protections."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_strategy_class():
    path = Path(__file__).resolve().parents[2] / "user_data/strategies/VolatilityMomentumStrategy.py"
    spec = importlib.util.spec_from_file_location("vol_mom_strategy", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.VolatilityMomentumStrategy


def test_strategy_protections_from_crypto_bot_config() -> None:
    VolatilityMomentumStrategy = _load_strategy_class()
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
    strat = VolatilityMomentumStrategy(cfg)
    assert isinstance(strat.protections, list)
    assert len(strat.protections) >= 3
    dd = next(
        p
        for p in strat.protections
        if p["method"] == "MaxDrawdown" and "lookback_period_candles" in p
    )
    assert dd["max_allowed_drawdown"] == 0.12
    daily = next(
        p for p in strat.protections if p["method"] == "MaxDrawdown" and p.get("lookback_period") == 1440
    )
    assert daily["max_allowed_drawdown"] == 0.025
    assert any(p["method"] == "StoplossGuard" for p in strat.protections)
