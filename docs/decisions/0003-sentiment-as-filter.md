# ADR 0003: Sentiment as filter, not decision-maker

## Status
Accepted

## Context
LLM trading agents show weak OOS evidence; Alpha Arena losses; Glasserman & Lin warn about entity look-ahead.

## Decision
News sentiment only blocks strongly negative entries or slightly sizes up positives. Anonymise entities for LLM. FinBERT first; LLM optional; neutral fallback. Risk rules always win.

## Consequences
Strategy remains momentum-driven; UI must show reasons; no LLM order placement APIs.
