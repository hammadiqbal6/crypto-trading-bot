"""Volatility-scaled time-series + cross-sectional momentum signals.

Evidence basis (see docs/research/):
- Hurst, Ooi & Pedersen 2017 — time-series momentum
- Liu, Tsyvinski & Wu JF 2022 — crypto cross-sectional momentum (large caps)
- Moreira & Muir 2017 — volatility targeting for risk control
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def time_series_momentum(
    close: pd.Series,
    *,
    lookback: int = 30,
) -> pd.Series:
    """Sign of cumulative return over lookback (skip most recent bar to reduce microstructure)."""
    if len(close) < lookback + 2:
        return pd.Series(0.0, index=close.index)
    # Exclude last return (common TSMOM implementation detail)
    lagged = close.shift(1)
    mom = lagged / lagged.shift(lookback) - 1.0
    return np.sign(mom).fillna(0.0)


def realized_vol_annual(
    close: pd.Series, *, window: int = 20, bars_per_year: float = 365 * 6
) -> pd.Series:
    """Annualised realised vol from log returns (default assumes 4h bars ≈ 6/day)."""
    rets = np.log(close / close.shift(1))
    vol = rets.rolling(window).std() * np.sqrt(bars_per_year)
    return vol.fillna(0.0)


def volatility_scale_factor(
    close: pd.Series,
    *,
    target_annual: float = 0.20,
    window: int = 20,
    bars_per_year: float = 365 * 6,
    cap: float = 2.0,
) -> pd.Series:
    vol = realized_vol_annual(close, window=window, bars_per_year=bars_per_year)
    scale = target_annual / vol.replace(0.0, np.nan)
    return scale.clip(lower=0.0, upper=cap).fillna(0.0)


def cross_sectional_momentum(
    closes: pd.DataFrame,
    *,
    lookback: int = 30,
) -> pd.Series:
    """
    Rank-based cross-sectional momentum across columns (pairs) at latest bar.
    Returns series of scores in [-1, 1] keyed by pair.
    """
    if closes.empty or len(closes) < lookback + 2:
        return pd.Series(dtype=float)
    lagged = closes.shift(1)
    mom = lagged.iloc[-1] / lagged.iloc[-1 - lookback] - 1.0
    # Rank to [-1, 1]
    ranks = mom.rank(method="average")
    n = len(ranks)
    if n <= 1:
        return pd.Series(0.0, index=mom.index)
    score = (ranks - 1) / (n - 1) * 2.0 - 1.0
    return score.fillna(0.0)


def combine_signals(
    ts_sign: float,
    xs_score: float,
    vol_scale: float,
    *,
    ts_weight: float = 0.7,
    xs_weight: float = 0.3,
) -> float:
    """Combine TS + XS into a position score scaled by vol targeting."""
    raw = ts_weight * ts_sign + xs_weight * xs_score
    return float(np.clip(raw * vol_scale, -2.0, 2.0))
