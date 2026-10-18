"""OHLCV download via CCXT public endpoints (no API key required)."""

from __future__ import annotations

import time
from pathlib import Path

import ccxt
import pandas as pd

from crypto_bot.utils.logging import get_logger

log = get_logger(__name__)

# Ordered by reliability from restricted egress environments (Bybit/Binance often geo-blocked).
PUBLIC_FALLBACKS = ("okx", "kraken", "gate", "bybit", "binance")


def fetch_ohlcv_df(
    symbol: str = "BTC/USDT",
    timeframe: str = "4h",
    *,
    exchange_id: str = "bybit",
    limit: int = 1000,
    since_ms: int | None = None,
) -> pd.DataFrame:
    """Fetch OHLCV, paginating backwards when the exchange caps page size."""
    exchange_class = getattr(ccxt, exchange_id)
    ex = exchange_class({"enableRateLimit": True})
    timeframe_ms = int(ex.parse_timeframe(timeframe) * 1000)
    all_rows: list[list[float]] = []
    # Start from "now" and walk backwards until we have `limit` bars
    end_ms = since_ms
    pages = 0
    max_pages = max(3, (limit // 100) + 2)
    while len(all_rows) < limit and pages < max_pages:
        pages += 1
        batch_limit = (
            min(300, limit - len(all_rows))
            if exchange_id == "okx"
            else min(1000, limit - len(all_rows))
        )
        params: dict[str, object] = {}
        fetch_since = None
        if end_ms is None and all_rows:
            # next older page: since = oldest - page*tf
            oldest = int(all_rows[0][0])
            fetch_since = oldest - batch_limit * timeframe_ms
        elif end_ms is not None and not all_rows:
            fetch_since = end_ms
        elif all_rows:
            oldest = int(all_rows[0][0])
            fetch_since = oldest - batch_limit * timeframe_ms
        raw = ex.fetch_ohlcv(
            symbol, timeframe=timeframe, since=fetch_since, limit=batch_limit, params=params
        )
        if not raw:
            break
        # Prepend older candles
        if all_rows and int(raw[-1][0]) >= int(all_rows[0][0]):
            # overlap / no progress
            raw = [r for r in raw if int(r[0]) < int(all_rows[0][0])]
            if not raw:
                break
        all_rows = raw + all_rows
        time.sleep(ex.rateLimit / 1000.0 if getattr(ex, "rateLimit", 0) else 0.05)
        if len(raw) < max(10, batch_limit // 5):
            break

    if not all_rows:
        log.warning(
            "ohlcv_empty",
            symbol=symbol,
            guidance="Empty OHLCV. Pair may be delisted or exchange returned no data.",
        )
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

    # Dedupe + trim
    seen: set[int] = set()
    uniq: list[list[float]] = []
    for row in all_rows:
        ts = int(row[0])
        if ts in seen:
            continue
        seen.add(ts)
        uniq.append(row)
    uniq = uniq[-limit:]
    df = pd.DataFrame(uniq, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"], unit="ms", utc=True)
    df = df.set_index("date").sort_index()
    return df


def fetch_ohlcv_with_fallback(
    symbol: str = "BTC/USDT",
    timeframe: str = "4h",
    *,
    preferred: str = "bybit",
    limit: int = 1000,
) -> tuple[pd.DataFrame, str]:
    """Try preferred exchange then PUBLIC_FALLBACKS. Returns (df, exchange_id used)."""
    tried: list[str] = []
    order = [preferred, *[e for e in PUBLIC_FALLBACKS if e != preferred]]
    errors: list[str] = []
    for eid in order:
        tried.append(eid)
        try:
            df = fetch_ohlcv_df(symbol, timeframe, exchange_id=eid, limit=limit)
            if not df.empty:
                if eid != preferred:
                    log.warning(
                        "ohlcv_fallback",
                        preferred=preferred,
                        used=eid,
                        guidance=(
                            f"{preferred} public market data failed; using {eid} instead. "
                            "Common causes: geo-block (CloudFront), rate limit, downtime."
                        ),
                    )
                return df, eid
        except Exception as e:
            errors.append(f"{eid}: {type(e).__name__}: {str(e)[:120]}")
            log.warning("ohlcv_fetch_failed", exchange=eid, error=str(e)[:200])
    guidance = (
        "All public OHLCV sources failed ("
        + "; ".join(errors[:3])
        + "). Check network/egress. Validation cannot run without candles."
    )
    log.error("ohlcv_all_failed", tried=tried, guidance=guidance)
    return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"]), preferred


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
    if not force:
        cached = sorted(data_dir.glob(f"*_{safe}_{timeframe}.csv"))
        # Prefer a cache that already has enough bars for walk-forward
        for path in reversed(cached):
            df = pd.read_csv(path, parse_dates=["date"], index_col="date")
            if getattr(df.index, "tz", None) is None:
                df.index = df.index.tz_localize("UTC")
            if len(df) >= min(limit, 500):
                return df
    df, used = fetch_ohlcv_with_fallback(symbol, timeframe, preferred=exchange_id, limit=limit)
    if not df.empty:
        path = data_dir / f"{used}_{safe}_{timeframe}.csv"
        df.to_csv(path)
        log.info("ohlcv_saved", path=str(path), rows=len(df), exchange=used)
    return df
