from crypto_bot.sentiment.anonymize import anonymize


def test_anonymize_replaces_bitcoin() -> None:
    result = anonymize("Bitcoin rallies as BTC ETF inflows surge")
    assert "Bitcoin" not in result.text
    assert "BTC" not in result.text
    assert "ENTITY_" in result.text
    assert result.mapping
