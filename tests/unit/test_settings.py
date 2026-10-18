"""Settings and live-trading gate tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from crypto_bot.config.settings import Settings, TradingMode


def test_demo_defaults() -> None:
    s = Settings(live_trading=False, trading_mode=TradingMode.DEMO)
    assert s.is_dry_run
    cfg = s.to_freqtrade_config()
    assert cfg["dry_run"] is True


def test_live_requires_confirm() -> None:
    with pytest.raises(ValidationError):
        Settings(live_trading=True, live_trading_confirm="")


def test_live_with_confirm() -> None:
    s = Settings(
        live_trading=True,
        live_trading_confirm="I_UNDERSTAND_LIVE_RISK",
        bybit_api_key="x",  # type: ignore[arg-type]
        bybit_api_secret="y",  # type: ignore[arg-type]
    )
    assert s.trading_mode == TradingMode.LIVE
    assert not s.is_dry_run


def test_missing_guidance() -> None:
    s = Settings(live_trading=False)
    tips = s.missing_required_guidance()
    assert any("Bybit" in t or "BINANCE" in t or "API" in t for t in tips)
