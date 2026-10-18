"""Typer CLI: dashboard, validate, news, freqtrade config export."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
import uvicorn

from crypto_bot import ACCURACY_DISCLAIMER, __version__
from crypto_bot.config.settings import get_settings
from crypto_bot.data.ohlcv import load_or_download
from crypto_bot.services.app_state import get_app_state
from crypto_bot.utils.logging import setup_logging
from crypto_bot.validation.walk_forward import walk_forward_momentum

app = typer.Typer(
    name="crypto-bot",
    help="AI crypto trading bot (demo/paper by default).",
    add_completion=False,
)


@app.callback()
def main() -> None:
    """Signalforge crypto-trading-bot CLI."""
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_json)


@app.command("version")
def version() -> None:
    typer.echo(f"crypto-trading-bot {__version__}")
    typer.echo(ACCURACY_DISCLAIMER)


@app.command("dashboard")
def dashboard(
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> None:
    """Start the FastAPI dashboard."""
    settings = get_settings()
    uvicorn.run(
        "crypto_bot.api.app:create_app",
        factory=True,
        host=host or settings.dashboard_host,
        port=port or settings.dashboard_port,
        reload=False,
    )


@app.command("export-freqtrade-config")
def export_freqtrade_config(
    out: Path = typer.Option(Path("config/freqtrade/config.json"), help="Output path"),
) -> None:
    """Write a freqtrade config JSON from settings (secrets from env)."""
    settings = get_settings()
    cfg = settings.to_freqtrade_config()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    typer.echo(f"Wrote {out} (dry_run={cfg['dry_run']})")


@app.command("download-data")
def download_data(
    symbol: str = "BTC/USDT",
    timeframe: str = "4h",
    limit: int = 1000,
) -> None:
    """Download public OHLCV via CCXT (no API key)."""
    settings = get_settings()
    df = load_or_download(
        symbol,
        timeframe,
        settings.user_data_dir / "data",
        exchange_id=settings.exchange_name.value,
        limit=limit,
        force=True,
    )
    typer.echo(f"Downloaded {len(df)} bars for {symbol} {timeframe}")


@app.command("validate")
def validate(
    symbol: str = "BTC/USDT",
    timeframe: str = "4h",
) -> None:
    """Run walk-forward + holdout validation with fees/slippage."""
    settings = get_settings()
    df = load_or_download(
        symbol,
        timeframe,
        settings.user_data_dir / "data",
        exchange_id=settings.exchange_name.value,
        limit=1000,
    )
    if df.empty:
        typer.secho("No data — check network.", fg=typer.colors.RED)
        raise typer.Exit(1)
    result = walk_forward_momentum(df["close"])
    typer.echo(json.dumps(result.to_dict(), indent=2, default=str))
    if not result.passed_gates:
        typer.secho(
            "Soft gates not passed — do not claim edge. Continue paper trading research.",
            fg=typer.colors.YELLOW,
        )


@app.command("refresh-news")
def refresh_news() -> None:
    """Fetch news + score sentiment; write strategy feature file."""
    state = get_app_state()
    articles = asyncio.run(state.refresh_news_and_sentiment())
    typer.echo(f"Articles: {len(articles)}")
    typer.echo(f"Wrote {state.settings.user_data_dir / 'sentiment_features.json'}")


@app.command("check-exchange")
def check_exchange() -> None:
    """Probe exchange connectivity and credentials."""
    state = get_app_state()
    health = state.refresh_exchange_health()
    typer.echo(json.dumps(health.to_dict(), indent=2))


if __name__ == "__main__":
    app()
