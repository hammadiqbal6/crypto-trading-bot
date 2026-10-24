"""Prove Bybit demo URL resolution: hostname trap vs enable_demo_trading."""

from __future__ import annotations

import ccxt
import pytest

from crypto_bot.config.settings import Settings, TradingMode
from crypto_bot.exchanges.health import _build_ccxt, resolve_bybit_api_public_url


def test_hostname_api_demo_is_malformed() -> None:
    """Historical bug: hostname=api-demo.bybit.com → api.api-demo.bybit.com."""
    ex = ccxt.bybit(
        {
            "enableRateLimit": True,
            "hostname": "api-demo.bybit.com",
            "options": {"defaultType": "spot"},
        }
    )
    url = resolve_bybit_api_public_url(ex)
    assert url == "https://api.api-demo.bybit.com"


def test_enable_demo_trading_resolves_correct_host() -> None:
    ex = ccxt.bybit({"enableRateLimit": True, "options": {"defaultType": "spot"}})
    ex.enable_demo_trading(True)
    url = resolve_bybit_api_public_url(ex)
    assert url == "https://api-demo.bybit.com"
    assert ex.options.get("enableDemoTrading") is True


def test_health_builder_uses_demo_trading_not_hostname() -> None:
    s = Settings(trading_mode=TradingMode.PAPER, bybit_demo=True)
    ex = _build_ccxt(s)
    url = resolve_bybit_api_public_url(ex)
    assert url == "https://api-demo.bybit.com"
    assert "api.api-demo" not in url


def test_live_bybit_keeps_mainnet_host() -> None:
    s = Settings(
        live_trading=True,
        live_trading_confirm="I_UNDERSTAND_LIVE_RISK",
        bybit_api_key="x",  # type: ignore[arg-type]
        bybit_api_secret="y",  # type: ignore[arg-type]
    )
    ex = _build_ccxt(s)
    url = resolve_bybit_api_public_url(ex)
    assert url == "https://api.bybit.com"
    assert ex.options.get("enableDemoTrading") in (False, None)


def test_exported_config_options_match_ccxt_demo_flag() -> None:
    s = Settings(trading_mode=TradingMode.DEMO, bybit_demo=True)
    cfg = s.to_freqtrade_config()
    assert cfg["exchange"]["demo_trading"] is True
    # Simulate what freqtrade does when demo_trading is True
    ex = ccxt.bybit(
        {
            "enableRateLimit": True,
            "options": {
                "defaultType": "spot",
                **cfg["exchange"]["ccxt_config"]["options"],
            },
        }
    )
    # options alone do not rewrite URLs — freqtrade calls the method:
    assert resolve_bybit_api_public_url(ex) == "https://api.bybit.com"
    ex.enable_demo_trading(True)
    assert resolve_bybit_api_public_url(ex) == "https://api-demo.bybit.com"


@pytest.mark.parametrize("mode", [TradingMode.PAPER, TradingMode.DEMO])
def test_paper_and_demo_bybit_use_demo_endpoints(mode: TradingMode) -> None:
    s = Settings(trading_mode=mode, bybit_demo=True)
    assert s.uses_demo_or_testnet_endpoints
    ex = _build_ccxt(s)
    assert "api-demo.bybit.com" in resolve_bybit_api_public_url(ex)
