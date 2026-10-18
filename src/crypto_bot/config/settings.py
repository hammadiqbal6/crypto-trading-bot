"""Pydantic settings with env + YAML, validated defaults, live-trading gate."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "config"
DEFAULT_YAML = CONFIG_DIR / "settings.yaml"


class TradingMode(StrEnum):
    DEMO = "demo"
    PAPER = "paper"
    LIVE = "live"


class ExchangeName(StrEnum):
    BYBIT = "bybit"
    BINANCE = "binance"


class LLMProvider(StrEnum):
    NONE = "none"
    GROQ = "groq"
    OLLAMA = "ollama"
    OPENAI = "openai"


class Settings(BaseSettings):
    """Application settings. All secrets via env; never commit .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Mode
    trading_mode: TradingMode = TradingMode.DEMO
    live_trading: bool = False
    live_trading_confirm: str = ""

    # Exchange
    exchange_name: ExchangeName = ExchangeName.BYBIT
    bybit_api_key: SecretStr = SecretStr("")
    bybit_api_secret: SecretStr = SecretStr("")
    bybit_demo: bool = True
    binance_testnet_api_key: SecretStr = SecretStr("")
    binance_testnet_api_secret: SecretStr = SecretStr("")

    # Optional market data
    coingecko_api_key: SecretStr = SecretStr("")

    # News
    news_enable_reddit: bool = False
    reddit_client_id: SecretStr = SecretStr("")
    reddit_client_secret: SecretStr = SecretStr("")
    reddit_user_agent: str = "crypto-trading-bot/0.1"

    # Sentiment / LLM
    llm_provider: LLMProvider = LLMProvider.GROQ
    groq_api_key: SecretStr = SecretStr("")
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-4o-mini"
    llm_rate_limit_rpm: int = Field(default=25, ge=1, le=60)
    sentiment_cache_ttl_hours: int = Field(default=24, ge=1)
    finbert_model: str = "ProsusAI/finbert"
    use_finbert: bool = True

    # Dashboard
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = Field(default=8080, ge=1, le=65535)
    dashboard_secret_key: SecretStr = SecretStr("change-me-to-a-long-random-string")

    # Risk
    max_open_trades: int = Field(default=3, ge=1, le=20)
    stake_currency: str = "USDT"
    dry_run_wallet: float = Field(default=10_000.0, gt=0)
    max_daily_loss_pct: float = Field(default=3.0, gt=0, le=50)
    max_drawdown_pct: float = Field(default=15.0, gt=0, le=80)
    stoploss_pct: float = Field(default=-0.05, lt=0, ge=-0.5)
    volatility_target_annual: float = Field(default=0.20, gt=0, le=1.0)
    position_size_cap_pct: float = Field(default=0.25, gt=0, le=1.0)

    # Strategy universe
    pair_whitelist: list[str] = Field(
        default_factory=lambda: [
            "BTC/USDT",
            "ETH/USDT",
            "SOL/USDT",
            "BNB/USDT",
            "XRP/USDT",
            "ADA/USDT",
            "AVAX/USDT",
            "DOGE/USDT",
            "LINK/USDT",
            "DOT/USDT",
        ]
    )
    timeframe: str = "4h"
    sentiment_block_threshold: float = Field(default=-0.55, ge=-1.0, le=0.0)
    sentiment_sizeup_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    sentiment_sizeup_factor: float = Field(default=1.15, ge=1.0, le=1.5)

    # Optional modules
    freqai_enabled: bool = False
    carry_enabled: bool = False

    # Logging / DB
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = False
    database_url: str = "sqlite+aiosqlite:///./user_data/crypto_bot.db"

    # Paths
    root_dir: Path = ROOT
    user_data_dir: Path = ROOT / "user_data"
    config_dir: Path = CONFIG_DIR

    @field_validator("pair_whitelist", mode="before")
    @classmethod
    def _parse_pairs(cls, v: Any) -> Any:
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        return v

    @model_validator(mode="after")
    def _live_trading_gate(self) -> Settings:
        """Live trading requires explicit flag + confirmation phrase."""
        if self.live_trading or self.trading_mode == TradingMode.LIVE:
            confirm = (self.live_trading_confirm or "").strip()
            if confirm != "I_UNDERSTAND_LIVE_RISK":
                msg = (
                    "Live trading is blocked. Set LIVE_TRADING=true AND "
                    "LIVE_TRADING_CONFIRM=I_UNDERSTAND_LIVE_RISK to enable. "
                    "Default remains demo/paper only."
                )
                raise ValueError(msg)
            if self.trading_mode != TradingMode.LIVE:
                object.__setattr__(self, "trading_mode", TradingMode.LIVE)
        else:
            # Force non-live modes to stay safe if somehow set without the gate
            if self.trading_mode.value == "live":
                object.__setattr__(self, "trading_mode", TradingMode.DEMO)
        return self

    @property
    def is_dry_run(self) -> bool:
        return self.trading_mode != TradingMode.LIVE or not self.live_trading

    @property
    def exchange_credentials_present(self) -> bool:
        if self.exchange_name == ExchangeName.BYBIT:
            return bool(self.bybit_api_key.get_secret_value()) and bool(
                self.bybit_api_secret.get_secret_value()
            )
        return bool(self.binance_testnet_api_key.get_secret_value()) and bool(
            self.binance_testnet_api_secret.get_secret_value()
        )

    @property
    def llm_credentials_present(self) -> bool:
        if self.llm_provider == LLMProvider.GROQ:
            return bool(self.groq_api_key.get_secret_value())
        if self.llm_provider == LLMProvider.OPENAI:
            return bool(self.openai_api_key.get_secret_value())
        return self.llm_provider == LLMProvider.OLLAMA

    def missing_required_guidance(self) -> list[str]:
        """Actionable guidance for missing/invalid config (shown in UI + logs)."""
        tips: list[str] = []
        if not self.exchange_credentials_present:
            if self.exchange_name == ExchangeName.BYBIT:
                tips.append(
                    "Bybit Demo API keys missing. Create at Bybit → Demo Trading → API Management, "
                    "set BYBIT_API_KEY / BYBIT_API_SECRET in .env. "
                    "Docs: https://bybit-exchange.github.io/docs/v5/demo"
                )
            else:
                tips.append(
                    "Binance Testnet keys missing. Get keys at https://testnet.binance.vision "
                    "and set BINANCE_TESTNET_API_KEY / BINANCE_TESTNET_API_SECRET. "
                    "Note: Binance is not licensed in Pakistan for live trading."
                )
        if self.llm_provider == LLMProvider.GROQ and not self.llm_credentials_present:
            tips.append(
                "GROQ_API_KEY missing. Sentiment will fall back to local FinBERT/neutral. "
                "Optional key: https://console.groq.com (free tier ~30 rpm)."
            )
        if self.news_enable_reddit and not (
            self.reddit_client_id.get_secret_value()
            and self.reddit_client_secret.get_secret_value()
        ):
            tips.append(
                "Reddit enabled but credentials missing. Set REDDIT_CLIENT_ID/SECRET "
                "or set NEWS_ENABLE_REDDIT=false. GDELT + RSS still work without keys."
            )
        if self.dashboard_secret_key.get_secret_value() == "change-me-to-a-long-random-string":
            tips.append(
                "DASHBOARD_SECRET_KEY is still the default. Change it before any deployment."
            )
        return tips

    def to_freqtrade_config(self) -> dict[str, Any]:
        """Build a freqtrade-compatible config dict (dry_run enforced unless live gated)."""
        dry = self.is_dry_run
        if self.exchange_name == ExchangeName.BYBIT:
            exchange: dict[str, Any] = {
                "name": "bybit",
                "key": self.bybit_api_key.get_secret_value(),
                "secret": self.bybit_api_secret.get_secret_value(),
                "ccxt_config": {
                    "enableRateLimit": True,
                    "options": {"defaultType": "spot"},
                },
                "ccxt_async_config": {"enableRateLimit": True},
                "pair_whitelist": self.pair_whitelist,
                "pair_blacklist": [],
            }
            if self.bybit_demo or dry:
                # Demo Trading endpoint
                exchange["ccxt_config"]["hostname"] = "api-demo.bybit.com"
                exchange["ccxt_async_config"]["hostname"] = "api-demo.bybit.com"
        else:
            exchange = {
                "name": "binance",
                "key": self.binance_testnet_api_key.get_secret_value(),
                "secret": self.binance_testnet_api_secret.get_secret_value(),
                "ccxt_config": {
                    "enableRateLimit": True,
                    "options": {"defaultType": "spot"},
                },
                "ccxt_async_config": {"enableRateLimit": True},
                "pair_whitelist": self.pair_whitelist,
                "pair_blacklist": [],
            }
            if dry:
                exchange["ccxt_config"]["urls"] = {
                    "api": {
                        "public": "https://testnet.binance.vision/api",
                        "private": "https://testnet.binance.vision/api",
                    }
                }

        cfg: dict[str, Any] = {
            "max_open_trades": self.max_open_trades,
            "stake_currency": self.stake_currency,
            "stake_amount": "unlimited",
            "tradable_balance_ratio": 0.99,
            "fiat_display_currency": "USD",
            "dry_run": dry,
            "dry_run_wallet": self.dry_run_wallet,
            "cancel_open_orders_on_exit": True,
            "trading_mode": "spot",
            "margin_mode": "",
            "unfilledtimeout": {
                "entry": 10,
                "exit": 10,
                "exit_timeout_count": 0,
                "unit": "minutes",
            },
            "entry_pricing": {
                "price_side": "same",
                "use_order_book": True,
                "order_book_top": 1,
                "price_last_balance": 0.0,
                "check_depth_of_market": {"enabled": False, "bids_to_ask_delta": 1},
            },
            "exit_pricing": {
                "price_side": "same",
                "use_order_book": True,
                "order_book_top": 1,
            },
            "exchange": exchange,
            "pairlists": [{"method": "StaticPairList"}],
            "timeframe": self.timeframe,
            "stoploss": self.stoploss_pct,
            "minimal_roi": {"0": 0.10, "60": 0.05, "180": 0.02, "360": 0},
            "bot_name": "crypto_bot",
            "initial_state": "running",
            "force_entry_enable": False,
            "internals": {"process_throttle_secs": 5},
            "strategy": "VolatilityMomentumStrategy",
            "strategy_path": str(self.user_data_dir / "strategies"),
            "user_data_dir": str(self.user_data_dir),
            "datadir": str(self.user_data_dir / "data"),
            "logfile": str(self.user_data_dir / "logs" / "freqtrade.log"),
            "db_url": f"sqlite:///{self.user_data_dir / 'tradesv3.sqlite'}",
            "api_server": {
                "enabled": False,
                "listen_ip_address": "127.0.0.1",
                "listen_port": 8081,
                "verbosity": "error",
                "jwt_secret_key": "change-me-freqtrade-jwt-not-for-production-use",
                "username": "freqtrader",
                "password": "changeme",
                "ws_token": "changeme",
            },
            "crypto_bot": {
                "sentiment_block_threshold": self.sentiment_block_threshold,
                "sentiment_sizeup_threshold": self.sentiment_sizeup_threshold,
                "sentiment_sizeup_factor": self.sentiment_sizeup_factor,
                "volatility_target_annual": self.volatility_target_annual,
                "position_size_cap_pct": self.position_size_cap_pct,
                "max_daily_loss_pct": self.max_daily_loss_pct,
                "max_drawdown_pct": self.max_drawdown_pct,
                "freqai_enabled": self.freqai_enabled,
                "carry_enabled": self.carry_enabled,
            },
        }
        if self.freqai_enabled:
            cfg["freqai"] = {
                "enabled": True,
                "purge_old_models": 2,
                "train_period_days": 30,
                "backtest_period_days": 7,
                "identifier": "vol_mom_gb",
                "feature_parameters": {
                    "include_timeframes": [self.timeframe],
                    "include_corr_pairlist": ["BTC/USDT", "ETH/USDT"],
                    "label_period_candles": 12,
                    "include_shifted_candles": 2,
                    "DI_threshold": 0.9,
                    "weight_factor": 0.9,
                    "principal_component_analysis": False,
                    "use_SVM_to_remove_outliers": True,
                    "indicator_periods_candles": [10, 20],
                },
                "data_split_parameters": {"test_size": 0.25, "shuffle": False},
                "model_training_parameters": {
                    "n_estimators": 200,
                    "learning_rate": 0.05,
                    "max_depth": 4,
                },
            }
        return cfg


def load_yaml_overrides(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_YAML
    if not p.exists():
        return {}
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return {}
    return data


@lru_cache
def get_settings(*, reload: bool = False) -> Settings:
    if reload:
        get_settings.cache_clear()
    yaml_data = load_yaml_overrides()
    # Env wins over YAML via pydantic; pass YAML as init defaults for non-secret keys
    safe = {
        k: v for k, v in yaml_data.items() if not str(k).endswith(("_key", "_secret", "_confirm"))
    }
    return Settings(**safe)
