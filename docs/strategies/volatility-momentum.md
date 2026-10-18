# VolatilityMomentumStrategy

## Idea
1. **Time-series momentum** (Hurst, Ooi & Pedersen 2017; Liu & Tsyvinski on crypto): sign of ~30-bar return on 4h bars.
2. **Cross-sectional tilt** among large caps (Liu, Tsyvinski & Wu JF 2022).
3. **Volatility targeting** (Moreira & Muir 2017) for position scaling / risk control.
4. **News sentiment filter**: block if score ≤ −0.55; size-up ×1.15 if ≥ 0.45.

## Not claimed
Does not claim >55% directional accuracy. Expect Sharpe 0.5–1.0 after costs *if* edge exists; many folds will fail soft gates — that is OK.

## Optional
- FreqAI gradient boosting on TA features with sliding-window retrain (`FREQAI_ENABLED`).
- Carry module separate (`CARRY_ENABLED`) — not part of this strategy's entries.
