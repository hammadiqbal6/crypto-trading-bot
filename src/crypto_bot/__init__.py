"""AI crypto trading bot — freqtrade engine, sentiment filter, validation gate."""

from __future__ import annotations

__version__ = "0.1.0"
__license__ = "GPL-3.0-or-later"

# Honest accuracy stance (never claim unproven edge):
ACCURACY_DISCLAIMER = (
    "No free method reliably beats ~51-55% daily directional accuracy out-of-sample. "
    "Target Sharpe after costs: 0.5-1.0. Halve any published edge."
)
