from crypto_bot.carry.module import CarryModule


def test_carry_disabled_by_default() -> None:
    m = CarryModule(enabled=False)
    opp = m.evaluate("BTC", 0.0005, 100.0, 100.5)
    assert opp.actionable is False
    assert "disabled" in opp.reason.lower()


def test_carry_enabled_candidate() -> None:
    m = CarryModule(enabled=True, min_funding_apr=0.05)
    # 0.0005 * 3 * 365 ≈ 54.75% APR
    opp = m.evaluate("BTC", 0.0005, 100.0, 100.2)
    assert opp.actionable is True
