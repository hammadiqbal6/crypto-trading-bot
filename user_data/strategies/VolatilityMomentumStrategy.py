"""Volatility-scaled TS + XS momentum with news-sentiment filter.

Freqtrade strategy (GPL-3.0 compatible — this project is GPL-3.0-or-later).
LLM/sentiment NEVER places trades or overrides stoploss / risk params.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pandas as pd
from freqtrade.strategy import IntParameter, IStrategy
from pandas import DataFrame

logger = logging.getLogger(__name__)

# Optional import of shared signal helpers when installed as package
try:
    from crypto_bot.config.protections import build_freqtrade_protections
    from crypto_bot.strategies.signals import (
        combine_signals,
        cross_sectional_momentum,
        time_series_momentum,
        volatility_scale_factor,
    )
except ImportError:  # pragma: no cover - standalone freqtrade path

    def build_freqtrade_protections(
        *,
        max_drawdown_pct: float,
        max_daily_loss_pct: float,
        timeframe: str = "4h",
    ) -> list[dict[str, Any]]:
        max_dd = abs(float(max_drawdown_pct)) / 100.0
        max_daily = abs(float(max_daily_loss_pct)) / 100.0
        return [
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 10_000,
                "trade_limit": 1,
                "stop_duration_candles": 10_000,
                "max_allowed_drawdown": max_dd,
                "calculation_mode": "equity",
            },
            {
                "method": "MaxDrawdown",
                "lookback_period": 1440,
                "trade_limit": 1,
                "unlock_at": "00:00",
                "max_allowed_drawdown": max_daily,
                "calculation_mode": "equity",
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 48,
                "trade_limit": 4,
                "stop_duration_candles": 12,
                "required_profit": 0.0,
            },
        ]

    def time_series_momentum(close: pd.Series, *, lookback: int = 30) -> pd.Series:
        lagged = close.shift(1)
        mom = lagged / lagged.shift(lookback) - 1.0
        return np.sign(mom).fillna(0.0)

    def volatility_scale_factor(
        close: pd.Series, *, target_annual: float = 0.20, window: int = 20, **_: Any
    ) -> pd.Series:
        rets = np.log(close / close.shift(1))
        vol = rets.rolling(window).std() * np.sqrt(365 * 6)
        return (target_annual / vol.replace(0, np.nan)).clip(0, 2).fillna(0.0)

    def cross_sectional_momentum(closes: pd.DataFrame, *, lookback: int = 30) -> pd.Series:
        lagged = closes.shift(1)
        mom = lagged.iloc[-1] / lagged.iloc[-1 - lookback] - 1.0
        ranks = mom.rank(method="average")
        n = len(ranks)
        if n <= 1:
            return pd.Series(0.0, index=mom.index)
        return ((ranks - 1) / (n - 1) * 2.0 - 1.0).fillna(0.0)

    def combine_signals(ts_sign: float, xs_score: float, vol_scale: float, **kwargs: Any) -> float:
        raw = 0.7 * ts_sign + 0.3 * xs_score
        return float(np.clip(raw * vol_scale, -2, 2))


class VolatilityMomentumStrategy(IStrategy):
    """
    Long-biased crypto large-cap momentum:
    1) Time-series trend (sign of ~30-bar return)
    2) Cross-sectional tilt vs universe
    3) Volatility scaling
    4) News sentiment filter via feature file (block / size-up)
    """

    INTERFACE_VERSION = 3
    timeframe = "4h"
    can_short = False
    startup_candle_count = 80
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    minimal_roi: ClassVar[dict[str, float]] = {"0": 0.10, "60": 0.05, "180": 0.02, "360": 0}
    stoploss = -0.05
    trailing_stop = False

    # Hyperopt-able (optional)
    mom_lookback = IntParameter(20, 60, default=30, space="buy")
    vol_window = IntParameter(10, 40, default=20, space="buy")

    # Sentiment feature file written by crypto_bot news service
    sentiment_path = Path("user_data/sentiment_features.json")

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        bot_cfg = config.get("crypto_bot") or {}
        self.sentiment_block = float(bot_cfg.get("sentiment_block_threshold", -0.55))
        self.sentiment_sizeup = float(bot_cfg.get("sentiment_sizeup_threshold", 0.45))
        self.sentiment_sizeup_factor = float(bot_cfg.get("sentiment_sizeup_factor", 1.15))
        self.vol_target = float(bot_cfg.get("volatility_target_annual", 0.20))
        self._max_drawdown_pct = float(bot_cfg.get("max_drawdown_pct", 15.0))
        self._max_daily_loss_pct = float(bot_cfg.get("max_daily_loss_pct", 3.0))
        self._xs_cache: dict[str, float] = {}
        self._last_reasons: dict[str, str] = {}
        # Wire risk settings into freqtrade ProtectionManager (live + backtest with
        # enable_protections). Previously only documented as "enforced externally".
        self.protections = build_freqtrade_protections(
            max_drawdown_pct=self._max_drawdown_pct,
            max_daily_loss_pct=self._max_daily_loss_pct,
            timeframe=str(config.get("timeframe") or self.timeframe),
        )

    def _load_sentiment(self) -> dict[str, float]:
        path = self.sentiment_path
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            scores = data.get("scores") or {}
            return {str(k): float(v) for k, v in scores.items()}
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning("sentiment_features_unreadable: %s — treating as neutral", e)
            return {}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        pair = metadata["pair"]
        lb = int(self.mom_lookback.value)
        vw = int(self.vol_window.value)
        close = dataframe["close"]
        dataframe["ts_mom"] = time_series_momentum(close, lookback=lb)
        dataframe["vol_scale"] = volatility_scale_factor(
            close, target_annual=self.vol_target, window=vw
        )
        # RSI / ATR as optional FreqAI features (also useful for exits)
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        dataframe["rsi"] = (100 - (100 / (1 + rs))).fillna(50)
        dataframe["atr"] = (dataframe["high"] - dataframe["low"]).rolling(14).mean().fillna(0)
        dataframe["ema_fast"] = close.ewm(span=12, adjust=False).mean()
        dataframe["ema_slow"] = close.ewm(span=48, adjust=False).mean()
        # Placeholder XS — filled in bot_loop_start from all pairs if available
        dataframe["xs_mom"] = self._xs_cache.get(pair, 0.0)
        sent = self._load_sentiment()
        coin = pair.split("/")[0]
        dataframe["sentiment"] = float(sent.get(pair, sent.get(coin, 0.0)))
        return dataframe

    def bot_loop_start(self, current_time: datetime, **kwargs: Any) -> None:
        """Refresh cross-sectional ranks when possible."""
        # Freqtrade may expose dataprovider
        dp = getattr(self, "dp", None)
        if dp is None:
            return
        closes: dict[str, pd.Series] = {}
        for pair in self.config.get("exchange", {}).get("pair_whitelist", []):
            try:
                ohlcv = dp.get_pair_dataframe(pair=pair, timeframe=self.timeframe)
                if ohlcv is not None and not ohlcv.empty:
                    closes[pair] = ohlcv["close"]
            except Exception:
                continue
        if len(closes) < 2:
            return
        df = pd.DataFrame(closes).dropna(how="all")
        scores = cross_sectional_momentum(df, lookback=int(self.mom_lookback.value))
        self._xs_cache = {str(k): float(v) for k, v in scores.items()}

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        pair = metadata["pair"]
        xs = float(self._xs_cache.get(pair, 0.0))
        dataframe["xs_mom"] = xs
        score = []
        enter = []
        reasons: list[str] = []
        for i in range(len(dataframe)):
            ts = float(dataframe["ts_mom"].iloc[i])
            vs = float(dataframe["vol_scale"].iloc[i])
            sent = float(dataframe["sentiment"].iloc[i])
            combined = combine_signals(ts, xs, vs)
            reason = f"ts={ts:.0f} xs={xs:.2f} vol={vs:.2f} sent={sent:.2f}"
            ok = (
                combined > 0.15
                and ts > 0
                and dataframe["ema_fast"].iloc[i] > dataframe["ema_slow"].iloc[i]
            )
            if sent <= self.sentiment_block:
                ok = False
                reason += " | BLOCKED negative news"
            score.append(combined)
            enter.append(1 if ok else 0)
            reasons.append(reason)
        dataframe["signal_score"] = score
        dataframe["enter_long"] = enter
        dataframe["enter_tag"] = reasons
        self._last_reasons[pair] = reasons[-1] if reasons else ""
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["exit_long"] = (
            (dataframe["ts_mom"] < 0)
            | (dataframe["ema_fast"] < dataframe["ema_slow"])
            | (dataframe["sentiment"] <= self.sentiment_block)
        ).astype(int)
        return dataframe

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs: Any,
    ) -> float:
        """Vol + sentiment size-up; never exceeds max_stake.

        Portfolio drawdown / daily-loss caps are enforced via ``protections``
        (MaxDrawdown + StoplossGuard) and the dashboard RiskManager.
        """
        sent_map = self._load_sentiment()
        coin = pair.split("/")[0]
        sent = float(sent_map.get(pair, sent_map.get(coin, 0.0)))
        stake = proposed_stake
        if sent >= self.sentiment_sizeup:
            stake = min(proposed_stake * self.sentiment_sizeup_factor, max_stake)
        if sent <= self.sentiment_block:
            return 0.0  # block entry
        if min_stake and stake < min_stake:
            return 0.0
        return float(min(stake, max_stake))

    # --- FreqAI hooks (optional; enabled via config) ---
    def feature_engineering_expand_all(
        self, dataframe: DataFrame, period: int, metadata: dict[str, Any], **kwargs: Any
    ) -> DataFrame:
        dataframe[f"%-rsi-period_{period}"] = dataframe["rsi"]
        dataframe[f"%-atr-period_{period}"] = dataframe["atr"]
        dataframe[f"%-mom-period_{period}"] = dataframe["ts_mom"]
        dataframe[f"%-volscale-period_{period}"] = dataframe["vol_scale"]
        return dataframe

    def feature_engineering_expand_basic(
        self, dataframe: DataFrame, metadata: dict[str, Any], **kwargs: Any
    ) -> DataFrame:
        dataframe["%-ema_ratio"] = dataframe["ema_fast"] / dataframe["ema_slow"]
        dataframe["%-sentiment"] = dataframe["sentiment"]
        return dataframe

    def feature_engineering_standard(
        self, dataframe: DataFrame, metadata: dict[str, Any], **kwargs: Any
    ) -> DataFrame:
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(
        self, dataframe: DataFrame, metadata: dict[str, Any], **kwargs: Any
    ) -> DataFrame:
        dataframe["&-s_close"] = dataframe["close"].shift(-12) / dataframe["close"] - 1.0
        return dataframe
