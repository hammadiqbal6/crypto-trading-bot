# ADR 0001: Use freqtrade as trading engine

## Status
Accepted

## Context
Need a maintained open-source execution engine with backtesting, pairlists, and FreqAI.

## Decision
Depend on freqtrade (GPL-3.0) via pip extra `[engine]`; do not vendor source. License this project GPL-3.0-or-later.

## Consequences
Must keep strategy IStrategy-compatible; contributors must accept GPL.
