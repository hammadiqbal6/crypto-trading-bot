"""OHLCV fallback unit tests (mocked exchanges)."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from crypto_bot.data.ohlcv import fetch_ohlcv_with_fallback


def _df(n: int = 5) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
    return pd.DataFrame(
        {
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.05,
            "volume": 10.0,
        },
        index=idx,
    )


def test_fallback_uses_second_exchange_on_failure() -> None:
    good = _df()

    def fake_fetch(symbol, timeframe, *, exchange_id="bybit", limit=1000, since_ms=None):
        if exchange_id == "bybit":
            raise RuntimeError("geo-blocked")
        if exchange_id == "okx":
            return good
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

    with patch("crypto_bot.data.ohlcv.fetch_ohlcv_df", side_effect=fake_fetch):
        df, used = fetch_ohlcv_with_fallback("BTC/USDT", "4h", preferred="bybit", limit=5)
    assert used == "okx"
    assert len(df) == 5


def test_all_fail_returns_empty() -> None:
    with patch(
        "crypto_bot.data.ohlcv.fetch_ohlcv_df",
        side_effect=RuntimeError("down"),
    ):
        df, used = fetch_ohlcv_with_fallback("BTC/USDT", "4h", preferred="bybit")
    assert df.empty
    assert used == "bybit"
