"""Risk manager hard-rule tests."""

from __future__ import annotations

import pytest

from crypto_bot.risk.manager import RiskManager
from crypto_bot.utils.errors import RiskBreachError


def test_kill_switch_on_drawdown() -> None:
    rm = RiskManager(max_drawdown_pct=10.0, starting_equity=10_000)
    rm.update_equity(10_000)
    rm.update_equity(8_500)  # 15% DD
    assert rm.state.killed
    with pytest.raises(RiskBreachError):
        rm.assert_can_enter()


def test_max_open_trades() -> None:
    rm = RiskManager(max_open_trades=2, starting_equity=10_000)
    rm.set_open_trades(2)
    with pytest.raises(RiskBreachError):
        rm.assert_can_enter()


def test_sentiment_block_and_sizeup() -> None:
    rm = RiskManager(position_size_cap_pct=0.25)
    size, reason = rm.apply_sentiment_size(
        0.1, -0.8, block_threshold=-0.55, sizeup_threshold=0.45, sizeup_factor=1.15
    )
    assert size == 0.0
    assert "blocked" in reason
    size2, reason2 = rm.apply_sentiment_size(
        0.1, 0.7, block_threshold=-0.55, sizeup_threshold=0.45, sizeup_factor=1.15
    )
    assert size2 == pytest.approx(0.115)
    assert "size-up" in reason2


def test_kill_switch_reset_requires_ack() -> None:
    rm = RiskManager(max_drawdown_pct=5.0, starting_equity=100)
    rm.update_equity(90)
    assert rm.state.killed
    with pytest.raises(RiskBreachError):
        rm.clear_kill_switch(operator_ack="nope")
    rm.clear_kill_switch(operator_ack="RESET_KILL_SWITCH")
    assert not rm.state.killed
