from __future__ import annotations

import numpy as np
import pandas as pd

from crypto_bot.validation.walk_forward import walk_forward_momentum


def test_walk_forward_runs_on_synthetic() -> None:
    idx = pd.date_range("2023-01-01", periods=600, freq="4h", tz="UTC")
    rng = np.random.default_rng(42)
    # Mild positive drift so strategy can find something; still may fail gates honestly
    rets = rng.normal(0.0004, 0.012, len(idx))
    close = pd.Series(100 * np.exp(np.cumsum(rets)), index=idx)
    result = walk_forward_momentum(
        close,
        train_bars=120,
        test_bars=40,
        holdout_bars=60,
        lookbacks=[20, 30],
    )
    assert len(result.folds) >= 1
    d = result.to_dict()
    assert "honest_disclaimer" in d
    assert "deflated_sharpe" in d
    assert "pbo" in d
