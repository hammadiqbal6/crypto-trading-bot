from crypto_bot.news.service import detect_coins, pair_to_coin


def test_detect_coins() -> None:
    assert "BTC" in detect_coins("Bitcoin hits new highs")
    assert "ETH" in detect_coins("Ethereum upgrade live")


def test_pair_to_coin() -> None:
    assert pair_to_coin("BTC/USDT") == "BTC"
