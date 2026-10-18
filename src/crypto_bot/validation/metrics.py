"""Performance metrics including deflated Sharpe and PBO (Bailey et al.)."""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
from scipy import stats


def sharpe_ratio(
    returns: Sequence[float] | np.ndarray,
    *,
    periods_per_year: float = 365 * 6,
    risk_free: float = 0.0,
) -> float:
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 2:
        return 0.0
    excess = r - risk_free / periods_per_year
    vol = excess.std(ddof=1)
    if vol < 1e-12:
        return 0.0
    return float(np.sqrt(periods_per_year) * excess.mean() / vol)


def max_drawdown(equity: Sequence[float] | np.ndarray) -> float:
    eq = np.asarray(equity, dtype=float)
    if len(eq) == 0:
        return 0.0
    peak = np.maximum.accumulate(eq)
    dd = (peak - eq) / np.where(peak == 0, 1.0, peak)
    return float(dd.max())


def expected_max_sharpe(n_trials: int) -> float:
    """Expected maximum Sharpe under N independent null trials (approx)."""
    if n_trials <= 1:
        return 0.0
    return float(
        (1 - np.euler_gamma) * stats.norm.ppf(1 - 1 / n_trials)
        + np.euler_gamma * stats.norm.ppf(1 - 1 / (n_trials * math.e))
    )


def sharpe_std_error(
    observed_sharpe: float,
    n_observations: int,
    *,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    if n_observations < 2:
        return float("inf")
    return math.sqrt(
        (
            1
            - skew * observed_sharpe
            + ((kurtosis - 1) / 4.0) * observed_sharpe**2
        )
        / (n_observations - 1)
    )


def deflated_sharpe_ratio(
    observed_sharpe: float,
    *,
    n_trials: int,
    n_observations: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    sharpe_benchmark: float = 0.0,
) -> float:
    """
    Deflated Sharpe Ratio (Bailey & López de Prado).

    Returns Φ(z) where z compares observed SR to a multiple-testing-adjusted
    null. Values near 1.0 suggest the SR is unlikely due to selection bias alone.
    Honest gate: require DSR high *and* positive OOS Sharpe after costs — never
    claim edge from in-sample SR alone.
    """
    if n_trials < 1 or n_observations < 2:
        return 0.0
    se = sharpe_std_error(
        observed_sharpe, n_observations, skew=skew, kurtosis=kurtosis
    )
    if not math.isfinite(se) or se < 1e-12:
        return 0.0
    # Null expected max SR ≈ expected_max_z * se (z-space → SR-space)
    sr0 = max(sharpe_benchmark, expected_max_sharpe(n_trials) * se)
    z = (observed_sharpe - sr0) / se
    return float(stats.norm.cdf(z))


def probability_of_backtest_overfitting(
    is_sharpes: Sequence[float],
    oos_sharpes: Sequence[float],
) -> float:
    """
    Simplified PBO estimate (Bailey et al.): fraction of trials whose OOS
    Sharpe falls below the median of the remaining trials.

    Lower is better. PBO >= 0.5 warns that IS selection may not generalise.
    """
    is_a = np.asarray(is_sharpes, dtype=float)
    oos_a = np.asarray(oos_sharpes, dtype=float)
    n = min(len(is_a), len(oos_a))
    if n < 2:
        return 1.0
    oos_a = oos_a[:n]
    fail = 0
    for i in range(n):
        others = np.delete(oos_a, i)
        if oos_a[i] < np.median(others):
            fail += 1
    return float(fail / n)


def apply_costs(
    returns: np.ndarray,
    *,
    turnover: np.ndarray,
    fee_bps: float = 6.0,
    slippage_bps: float = 4.0,
) -> np.ndarray:
    """Subtract fees+slippage * turnover from period returns."""
    cost = (fee_bps + slippage_bps) / 10_000.0
    return returns - turnover * cost
