"""OHLCV download via CCXT public endpoints (no API key required)."""

from __future__ import annotations

from pathlib import Path

import ccxt
import pandas as pd

from crypto_bot.utils.logging import get_logger

log = get_logger(__name__)


def fetch_ohlcv_df(
    symbol: str = "BTC/USDT",
    timeframe: str = "4h",
    *,
    exchange_id: str = "bybit",
    limit: int = 1000,
    since_ms: int | None = None,
) -> pd.DataFrame:
    exchange_class = getattr(ccxt, exchange_id)
    ex = exchange_class({"enableRateLimit": True})
    raw = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=since_ms, limit=limit)
    if not raw:
        log.warning(
            "ohlcv_empty",
            symbol=symbol,
            guidance="Empty OHLCV. Pair may be delisted or exchange returned no data.",
        )
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(raw, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"], unit="ms", utc=True)
    df = df.set_index("date").sort_index()
    return df


def load_or_download(
    symbol: str,
    timeframe: str,
    data_dir: Path,
    *,
    exchange_id: str = "bybit",
    limit: int = 1000,
    force: bool = False,
) -> pd.DataFrame:
    data_dir.mkdir(parents=True, exist_ok=True)
    safe = symbol.replace("/", "_")
    path = data_dir / f"{exchange_id}_{safe}_{timeframe}.csv"
    if path.exists() and not force:
        df = pd.read_csv(path, parse_dates=["date"], index_col="date")
        if getattr(df.index, "tz", None) is None:
            df.index = df.index.tz_localize("UTC")
        return df
    df = fetch_ohlcv_df(symbol, timeframe, exchange_id=exchange_id, limit=limit)
    if not df.empty:
        df.to_csv(path)
        log.info("ohlcv_saved", path=str(path), rows=len(df))
    return df
