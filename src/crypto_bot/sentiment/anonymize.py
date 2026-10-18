"""Anonymise coin/entity names to reduce LLM look-ahead bias (Glasserman & Lin)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from crypto_bot.news.service import COIN_ALIASES

# Broader entity list for headlines
_EXTRA_ENTITIES = {
    "COINBASE": ("coinbase",),
    "BINANCE": ("binance",),
    "BYBIT": ("bybit",),
    "BLACKROCK": ("blackrock",),
    "FIDELITY": ("fidelity",),
    "SEC": (" sec ", "securities and exchange commission"),
    "FED": ("federal reserve", " the fed ", "fomc"),
}


@dataclass
class AnonymizedText:
    text: str
    mapping: dict[str, str]  # TOKEN -> original


def anonymize(text: str) -> AnonymizedText:
    """Replace known entities with ENTITY_N tokens."""
    mapping: dict[str, str] = {}
    out = f" {text} "
    idx = 1

    entities: list[tuple[str, tuple[str, ...]]] = [
        *[(k, v) for k, v in COIN_ALIASES.items()],
        *[(k, v) for k, v in _EXTRA_ENTITIES.items()],
    ]
    # Longer aliases first
    flat: list[tuple[str, str]] = []
    for canon, aliases in entities:
        for a in aliases:
            flat.append((a, canon))
    flat.sort(key=lambda x: len(x[0]), reverse=True)

    used_canons: dict[str, str] = {}
    for alias, canon in flat:
        if canon in used_canons:
            token = used_canons[canon]
        else:
            token = f"ENTITY_{idx}"
            used_canons[canon] = token
            mapping[token] = canon
            idx += 1
        pattern = re.compile(rf"(?i)\b{re.escape(alias.strip())}\b")
        out, n = pattern.subn(token, out)
        if n == 0 and canon in mapping.values() and n == 0:
            # cleanup unused token
            pass
    # Drop unused tokens from mapping
    present = {t for t in mapping if t in out}
    mapping = {t: mapping[t] for t in present}
    return AnonymizedText(text=out.strip(), mapping=mapping)
