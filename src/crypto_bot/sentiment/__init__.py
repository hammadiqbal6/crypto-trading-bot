"""Sentiment: local FinBERT first, pluggable LLM with anonymisation + cache."""

from crypto_bot.sentiment.pipeline import SentimentPipeline, SentimentResult

__all__ = ["SentimentPipeline", "SentimentResult"]
