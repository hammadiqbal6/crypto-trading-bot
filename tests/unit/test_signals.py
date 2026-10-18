"""Momentum signal unit tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from crypto_bot.strategies.signals import (
    combine_signals,
    cross_sectional_momentum,
    time_series_momentum,
    volatility_scale_factor,
)


def test_time_series_momentum_uptrend() -> None:
    idx = pd.date_range("2024-01-01", periods=80, freq="4h", tz="UTC")
    close = pd.Series(np.linspace(100, 200, 80), index=idx)
    mom = time_series_momentum(close, lookback=20)
    assert mom.iloc[-1] == 1.0


def test_cross_sectional_ranks() -> None:
    idx = pd.date_range("2024-01-01", periods=60, freq="4h", tz="UTC")
    a = pd.Series(np.linspace(1, 2, 60), index=idx)
    b = pd.Series(np.linspace(1, 1.1, 60), index=idx)
    c = pd.Series(np.linspace(1, 0.8, 60), index=idx)
    scores = cross_sectional_momentum(pd.DataFrame({"A": a, "B": b, "C": c}), lookback=20)
    assert scores["A"] > scores["C"]


def test_vol_scale_and_combine() -> None:
    idx = pd.date_range("2024-01-01", periods=100, freq="4h", tz="UTC")
    rng = np.random.default_rng(0)
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 100))), index=idx)
    scale = volatility_scale_factor(close, target_annual=0.2)
    assert (scale >= 0).all()
    assert combine_signals(1.0, 0.5, 1.0) > 0
