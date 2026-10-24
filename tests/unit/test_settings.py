"""Settings, live-trading gate, demo routing, and protections export tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from crypto_bot.config.protections import build_freqtrade_protections
from crypto_bot.config.settings import LIVE_CONFIRM_PHRASE, Settings, TradingMode


def test_paper_defaults_are_dry_run() -> None:
    s = Settings(live_trading=False, trading_mode=TradingMode.PAPER)
    assert s.is_dry_run
    assert not s.is_exchange_demo
    assert not s.is_live
    cfg = s.to_freqtrade_config()
    assert cfg["dry_run"] is True
    assert "strategy_path" not in cfg


def test_live_requires_confirm() -> None:
    with pytest.raises(ValidationError):
        Settings(live_trading=True, live_trading_confirm="")


def test_live_with_confirm() -> None:
    s = Settings(
        live_trading=True,
        live_trading_confirm=LIVE_CONFIRM_PHRASE,
        bybit_api_key="x",  # type: ignore[arg-type]
        bybit_api_secret="y",  # type: ignore[arg-type]
        bybit_demo=True,  # forced off for mainnet
    )
    assert s.trading_mode == TradingMode.LIVE
    assert not s.is_dry_run
    assert s.is_live
    assert s.bybit_demo is False
    cfg = s.to_freqtrade_config()
    assert cfg["dry_run"] is False
    assert cfg["exchange"].get("demo_trading") is not True
    assert "enableDemoTrading" not in cfg["exchange"]["ccxt_config"]["options"]


def test_exchange_demo_mode_disables_dry_run() -> None:
    s = Settings(
        trading_mode=TradingMode.DEMO,
        bybit_demo=True,
        bybit_api_key="x",  # type: ignore[arg-type]
        bybit_api_secret="y",  # type: ignore[arg-type]
    )
    assert not s.is_dry_run
    assert s.is_exchange_demo
    assert s.uses_demo_or_testnet_endpoints
    cfg = s.to_freqtrade_config()
    assert cfg["dry_run"] is False
    assert cfg["exchange"]["demo_trading"] is True
    assert cfg["exchange"]["ccxt_config"]["options"]["enableDemoTrading"] is True
    assert cfg["exchange"]["ccxt_async_config"]["options"]["enableDemoTrading"] is True
    # Malformed hostname must not appear
    assert cfg["exchange"]["ccxt_config"].get("hostname") != "api-demo.bybit.com"
    assert "hostname" not in cfg["exchange"]["ccxt_config"]


def test_demo_mode_requires_bybit_demo_flag() -> None:
    with pytest.raises(ValidationError, match="BYBIT_DEMO"):
        Settings(trading_mode=TradingMode.DEMO, bybit_demo=False)


def test_binance_demo_uses_testnet_urls() -> None:
    s = Settings(
        trading_mode=TradingMode.DEMO,
        exchange_name="binance",  # type: ignore[arg-type]
        binance_testnet_api_key="x",  # type: ignore[arg-type]
        binance_testnet_api_secret="y",  # type: ignore[arg-type]
    )
    cfg = s.to_freqtrade_config()
    assert cfg["dry_run"] is False
    urls = cfg["exchange"]["ccxt_config"]["urls"]["api"]
    assert "testnet.binance.vision" in urls["public"]
    assert "testnet.binance.vision" in urls["private"]


def test_protections_mapped_from_risk_settings() -> None:
    s = Settings(
        trading_mode=TradingMode.PAPER,
        max_drawdown_pct=15.0,
        max_daily_loss_pct=3.0,
    )
    cfg = s.to_freqtrade_config()
    assert cfg["enable_protections"] is True
    prots = cfg["crypto_bot"]["protections"]
    assert len(prots) >= 3
    methods = [p["method"] for p in prots]
    assert methods.count("MaxDrawdown") == 2
    assert "StoplossGuard" in methods
    dd = next(p for p in prots if p["method"] == "MaxDrawdown" and "lookback_period_candles" in p)
    assert dd["max_allowed_drawdown"] == pytest.approx(0.15)
    daily = next(
        p for p in prots if p["method"] == "MaxDrawdown" and p.get("lookback_period") == 1440
    )
    assert daily["max_allowed_drawdown"] == pytest.approx(0.03)


def test_build_freqtrade_protections_helper() -> None:
    prots = build_freqtrade_protections(max_drawdown_pct=10, max_daily_loss_pct=2)
    assert prots[0]["max_allowed_drawdown"] == pytest.approx(0.10)
    assert prots[1]["max_allowed_drawdown"] == pytest.approx(0.02)


def test_missing_guidance() -> None:
    s = Settings(live_trading=False, trading_mode=TradingMode.PAPER)
    tips = s.missing_required_guidance()
    # Paper mode does not require exchange keys
    assert isinstance(tips, list)


def test_demo_missing_keys_guidance() -> None:
    s = Settings(trading_mode=TradingMode.DEMO, bybit_demo=True)
    tips = s.missing_required_guidance()
    assert any("Bybit" in t or "Demo" in t for t in tips)
