"""Walk-forward + holdout validation for the momentum strategy (vectorbt-friendly)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from crypto_bot.strategies.signals import time_series_momentum, volatility_scale_factor
from crypto_bot.utils.logging import get_logger
from crypto_bot.validation.metrics import (
    apply_costs,
    deflated_sharpe_ratio,
    max_drawdown,
    probability_of_backtest_overfitting,
    sharpe_ratio,
)

log = get_logger(__name__)


@dataclass
class WalkForwardFold:
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    is_sharpe: float
    oos_sharpe: float
    oos_return: float
    lookback: int


@dataclass
class WalkForwardResult:
    folds: list[WalkForwardFold] = field(default_factory=list)
    holdout_sharpe: float = 0.0
    holdout_return: float = 0.0
    holdout_max_dd: float = 0.0
    mean_oos_sharpe: float = 0.0
    deflated_sharpe: float = 0.0
    pbo: float = 1.0
    fee_bps: float = 6.0
    slippage_bps: float = 4.0
    n_trials: int = 0
    notes: list[str] = field(default_factory=list)
    passed_gates: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "folds": [f.__dict__ for f in self.folds],
            "holdout_sharpe": self.holdout_sharpe,
            "holdout_return": self.holdout_return,
            "holdout_max_dd": self.holdout_max_dd,
            "mean_oos_sharpe": self.mean_oos_sharpe,
            "deflated_sharpe": self.deflated_sharpe,
            "pbo": self.pbo,
            "fee_bps": self.fee_bps,
            "slippage_bps": self.slippage_bps,
            "n_trials": self.n_trials,
            "notes": self.notes,
            "passed_gates": self.passed_gates,
            "honest_disclaimer": (
                "No free method reliably beats ~51-55% daily directional accuracy OOS. "
                "Target Sharpe after costs 0.5-1.0. Halve published edges."
            ),
        }


def _backtest_tsmom(
    close: pd.Series,
    *,
    lookback: int,
    vol_target: float = 0.20,
    fee_bps: float = 6.0,
    slippage_bps: float = 4.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (net_returns, turnover, equity). Long/flat based on TSMOM * vol scale."""
    signal = time_series_momentum(close, lookback=lookback).clip(lower=0.0)  # long/flat
    scale = volatility_scale_factor(close, target_annual=vol_target)
    pos = (signal * scale).clip(0.0, 1.0).fillna(0.0)
    rets = close.pct_change().fillna(0.0)
    # Position from prior bar (no lookahead)
    pos_lag = pos.shift(1).fillna(0.0)
    gross = pos_lag.to_numpy() * rets.to_numpy()
    turnover = np.abs(np.diff(pos_lag.to_numpy(), prepend=0.0))
    net = apply_costs(gross, turnover=turnover, fee_bps=fee_bps, slippage_bps=slippage_bps)
    equity = np.cumprod(1.0 + net)
    return net, turnover, equity


def walk_forward_momentum(
    close: pd.Series,
    *,
    lookbacks: list[int] | None = None,
    train_bars: int = 180,
    test_bars: int = 60,
    holdout_bars: int = 90,
    fee_bps: float = 6.0,
    slippage_bps: float = 4.0,
    vol_target: float = 0.20,
) -> WalkForwardResult:
    """
    Rolling walk-forward: on each fold pick best lookback by IS Sharpe,
    evaluate OOS; final untouched holdout with the median selected lookback.
    """
    lookbacks = lookbacks or [20, 30, 40, 50]
    result = WalkForwardResult(fee_bps=fee_bps, slippage_bps=slippage_bps, n_trials=len(lookbacks))
    close = close.dropna()
    n = len(close)
    if n < train_bars + test_bars + holdout_bars + 50:
        result.notes.append(
            f"Insufficient bars ({n}). Need train+test+holdout+warmup. "
            "Download more history via `make download-data`."
        )
        return result

    holdout = close.iloc[-holdout_bars:]
    research = close.iloc[:-holdout_bars]
    cursor = 0
    is_s: list[float] = []
    oos_s: list[float] = []
    chosen: list[int] = []

    while cursor + train_bars + test_bars <= len(research):
        train = research.iloc[cursor : cursor + train_bars]
        test = research.iloc[cursor + train_bars : cursor + train_bars + test_bars]
        best_lb = lookbacks[0]
        best_is = -1e9
        for lb in lookbacks:
            net, _, _ = _backtest_tsmom(
                train,
                lookback=lb,
                vol_target=vol_target,
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
            )
            s = sharpe_ratio(net)
            if s > best_is:
                best_is = s
                best_lb = lb
        net_oos, _, _ = _backtest_tsmom(
            pd.concat([train.iloc[-best_lb - 5 :], test]),
            lookback=best_lb,
            vol_target=vol_target,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
        )
        # Only score the test portion
        oos_slice = net_oos[-len(test) :]
        oos_sh = sharpe_ratio(oos_slice)
        fold = WalkForwardFold(
            train_start=str(train.index[0]),
            train_end=str(train.index[-1]),
            test_start=str(test.index[0]),
            test_end=str(test.index[-1]),
            is_sharpe=float(best_is),
            oos_sharpe=float(oos_sh),
            oos_return=float(np.prod(1 + oos_slice) - 1),
            lookback=best_lb,
        )
        result.folds.append(fold)
        is_s.append(best_is)
        oos_s.append(oos_sh)
        chosen.append(best_lb)
        cursor += test_bars

    if not result.folds:
        result.notes.append("No walk-forward folds produced.")
        return result

    result.mean_oos_sharpe = float(np.mean(oos_s))
    result.pbo = probability_of_backtest_overfitting(is_s, oos_s)
    med_lb = int(np.median(chosen))
    # Untouched holdout
    net_h, _, eq_h = _backtest_tsmom(
        pd.concat([research.iloc[-med_lb - 5 :], holdout]),
        lookback=med_lb,
        vol_target=vol_target,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
    )
    hold_rets = net_h[-len(holdout) :]
    result.holdout_sharpe = sharpe_ratio(hold_rets)
    result.holdout_return = float(np.prod(1 + hold_rets) - 1)
    result.holdout_max_dd = max_drawdown(eq_h[-len(holdout) :])
    result.deflated_sharpe = deflated_sharpe_ratio(
        result.mean_oos_sharpe,
        n_trials=len(lookbacks) * max(len(result.folds), 1),
        n_observations=test_bars * len(result.folds),
    )
    result.notes.append(
        f"Selected lookbacks per fold: {chosen}; holdout used median lookback={med_lb}."
    )
    result.notes.append(
        "Gates (soft): mean OOS Sharpe > 0, DSR > 0.5, PBO < 0.5, holdout Sharpe > 0 after costs."
    )
    result.passed_gates = (
        result.mean_oos_sharpe > 0
        and result.deflated_sharpe > 0.5
        and result.pbo < 0.5
        and result.holdout_sharpe > 0
    )
    log.info(
        "walk_forward_done",
        folds=len(result.folds),
        mean_oos=result.mean_oos_sharpe,
        holdout=result.holdout_sharpe,
        dsr=result.deflated_sharpe,
        pbo=result.pbo,
        passed=result.passed_gates,
    )
    return result
