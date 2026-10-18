"""Exchange connectivity, clock drift, and credential checks with guidance."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import ccxt

from crypto_bot.config.settings import ExchangeName, Settings
from crypto_bot.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class ExchangeHealth:
    ok: bool
    exchange: str
    dry_run: bool
    latency_ms: float | None = None
    clock_drift_ms: float | None = None
    balance_ok: bool | None = None
    message: str = ""
    guidance: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "exchange": self.exchange,
            "dry_run": self.dry_run,
            "latency_ms": self.latency_ms,
            "clock_drift_ms": self.clock_drift_ms,
            "balance_ok": self.balance_ok,
            "message": self.message,
            "guidance": self.guidance,
            "details": self.details,
        }


def _build_ccxt(settings: Settings) -> ccxt.Exchange:
    if settings.exchange_name == ExchangeName.BYBIT:
        ex = ccxt.bybit(
            {
                "apiKey": settings.bybit_api_key.get_secret_value() or None,
                "secret": settings.bybit_api_secret.get_secret_value() or None,
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            }
        )
        if settings.bybit_demo or settings.is_dry_run:
            # Demo Trading REST host
            ex.urls["api"] = ex.urls.get("api", {})
            if isinstance(ex.urls["api"], dict):
                for k in list(ex.urls["api"].keys()):
                    ex.urls["api"][k] = "https://api-demo.bybit.com"
            ex.hostname = "api-demo.bybit.com"
        return ex
    ex = ccxt.binance(
        {
            "apiKey": settings.binance_testnet_api_key.get_secret_value() or None,
            "secret": settings.binance_testnet_api_secret.get_secret_value() or None,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        }
    )
    if settings.is_dry_run:
        ex.set_sandbox_mode(True)
    return ex


def check_exchange_health(settings: Settings) -> ExchangeHealth:
    guidance = list(settings.missing_required_guidance())
    name = settings.exchange_name.value
    dry = settings.is_dry_run
    if not settings.exchange_credentials_present:
        return ExchangeHealth(
            ok=False,
            exchange=name,
            dry_run=dry,
            message="API credentials missing",
            guidance=guidance
            or [
                "Add exchange API keys to .env. Public market data still works via CCXT without keys."
            ],
        )
    try:
        ex = _build_ccxt(settings)
        t0 = time.perf_counter()
        ticker = ex.fetch_ticker("BTC/USDT")
        latency = (time.perf_counter() - t0) * 1000
        drift = None
        try:
            server_ms = ex.fetch_time()
            if server_ms:
                drift = abs(server_ms - int(time.time() * 1000))
                if drift > 1000:
                    guidance.append(
                        f"Clock drift {drift:.0f}ms. Sync NTP before live/demo private calls."
                    )
        except Exception:
            pass
        balance_ok = None
        try:
            bal = ex.fetch_balance()
            balance_ok = True
            free = (bal.get("free") or {}).get(settings.stake_currency)
            if free is not None and float(free) <= 0 and not dry:
                guidance.append(
                    f"No free {settings.stake_currency} balance. Fund demo wallet or lower stakes."
                )
                balance_ok = False
        except ccxt.AuthenticationError:
            guidance.append(
                "Authentication failed. Regenerate API keys; ensure Demo keys for api-demo.bybit.com."
            )
            return ExchangeHealth(
                ok=False,
                exchange=name,
                dry_run=dry,
                latency_ms=latency,
                clock_drift_ms=drift,
                message="Authentication failed",
                guidance=guidance,
            )
        except ccxt.NetworkError as e:
            guidance.append(
                f"Network/exchange downtime: {e}. Retry later; bot will keep using cached data."
            )
            return ExchangeHealth(
                ok=False,
                exchange=name,
                dry_run=dry,
                latency_ms=latency,
                message="Network error",
                guidance=guidance,
            )
        except Exception as e:
            log.warning("balance_check_skipped", error=str(e))
        last = ticker.get("last")
        return ExchangeHealth(
            ok=True,
            exchange=name,
            dry_run=dry,
            latency_ms=round(latency, 1),
            clock_drift_ms=drift,
            balance_ok=balance_ok,
            message=f"BTC/USDT last={last}",
            guidance=guidance,
            details={"btc_last": last},
        )
    except ccxt.NetworkError as e:
        return ExchangeHealth(
            ok=False,
            exchange=name,
            dry_run=dry,
            message=str(e),
            guidance=[
                "Exchange unreachable. Check internet, firewall, and exchange status pages.",
                *guidance,
            ],
        )
    except Exception as e:
        return ExchangeHealth(
            ok=False,
            exchange=name,
            dry_run=dry,
            message=str(e),
            guidance=["Unexpected exchange error. See logs.", *guidance],
        )
