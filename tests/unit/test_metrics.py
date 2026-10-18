"""Validation metrics tests."""

from __future__ import annotations

import numpy as np

from crypto_bot.validation.metrics import (
    deflated_sharpe_ratio,
    probability_of_backtest_overfitting,
    sharpe_ratio,
)


def test_sharpe_positive_on_drift() -> None:
    rng = np.random.default_rng(1)
    rets = rng.normal(0.001, 0.01, 500)
    assert sharpe_ratio(rets) > 0


def test_pbo_bounds() -> None:
    is_s = [1.0, 0.5, 0.2, 0.1]
    oos = [0.1, 0.4, 0.3, 0.5]
    pbo = probability_of_backtest_overfitting(is_s, oos)
    assert 0.0 <= pbo <= 1.0


def test_deflated_sharpe_range() -> None:
    dsr = deflated_sharpe_ratio(0.2, n_trials=10, n_observations=200)
    assert 0.0 <= dsr <= 1.0
