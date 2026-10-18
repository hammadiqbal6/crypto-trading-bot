"""FastAPI app: JSON API + server-rendered dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from crypto_bot import ACCURACY_DISCLAIMER, __version__
from crypto_bot.config.settings import get_settings
from crypto_bot.data.ohlcv import load_or_download
from crypto_bot.services.app_state import get_app_state
from crypto_bot.utils.errors import CryptoBotError, RiskBreachError
from crypto_bot.utils.logging import get_logger, setup_logging
from crypto_bot.validation.walk_forward import walk_forward_momentum

log = get_logger(__name__)

DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"
TEMPLATES = Jinja2Templates(directory=str(DASHBOARD_DIR / "templates"))


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_json)
    app = FastAPI(
        title="crypto-trading-bot",
        version=__version__,
        description="Demo/paper AI crypto trading bot — freqtrade + sentiment + validation",
    )
    static_dir = DASHBOARD_DIR / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.exception_handler(CryptoBotError)
    async def _crypto_err(_req: Request, exc: CryptoBotError) -> JSONResponse:
        return JSONResponse(status_code=400, content=exc.to_dict())

    def _ctx(**extra: Any) -> dict[str, Any]:
        state = get_app_state()
        return {
            "status": state.status_dict(),
            "risk": state.risk_state().to_dict(),
            "health": state.exchange_health.to_dict() if state.exchange_health else None,
            "articles": [a.to_dict() for a in state.articles[:40]],
            "signals": [s.to_dict() for s in state.signals],
            "validation": state.validation.to_dict() if state.validation else None,
            "logs": state.logs[-80:],
            "guidance": state.settings.missing_required_guidance(),
            "news_errors": state.news.last_errors,
            "disclaimer": ACCURACY_DISCLAIMER,
            "version": __version__,
            "onboarding_step": state.onboarding_step,
            **extra,
        }

    # ---- Pages ----
    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(request, "dashboard.html", _ctx(page="overview"))

    @app.get("/setup", response_class=HTMLResponse)
    async def setup(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(request, "setup.html", _ctx(page="setup"))

    @app.get("/news", response_class=HTMLResponse)
    async def news_page(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(request, "news.html", _ctx(page="news"))

    @app.get("/validation", response_class=HTMLResponse)
    async def validation_page(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(request, "validation.html", _ctx(page="validation"))

    @app.get("/risk", response_class=HTMLResponse)
    async def risk_page(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(request, "risk.html", _ctx(page="risk"))

    @app.get("/logs", response_class=HTMLResponse)
    async def logs_page(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(request, "logs.html", _ctx(page="logs"))

    # ---- Actions ----
    @app.post("/actions/refresh-news")
    async def action_refresh_news() -> RedirectResponse:
        state = get_app_state()
        try:
            await state.refresh_news_and_sentiment()
        except Exception as e:  # noqa: BLE001
            state.add_log(f"News refresh failed: {e}")
        return RedirectResponse("/news", status_code=303)

    @app.post("/actions/check-exchange")
    async def action_check_exchange() -> RedirectResponse:
        get_app_state().refresh_exchange_health()
        return RedirectResponse("/", status_code=303)

    @app.post("/actions/run-validation")
    async def action_run_validation() -> RedirectResponse:
        state = get_app_state()
        state.add_log("Starting walk-forward validation (BTC/USDT)…")
        try:
            df = load_or_download(
                "BTC/USDT",
                state.settings.timeframe,
                state.settings.user_data_dir / "data",
                exchange_id="bybit",
                limit=1000,
            )
            if df.empty:
                state.add_log("Validation aborted: no OHLCV data.")
            else:
                result = walk_forward_momentum(df["close"])
                state.validation = result
                state.add_log(
                    f"Validation done: OOS Sharpe={result.mean_oos_sharpe:.2f} "
                    f"holdout={result.holdout_sharpe:.2f} DSR={result.deflated_sharpe:.2f} "
                    f"PBO={result.pbo:.2f} passed={result.passed_gates}"
                )
        except Exception as e:  # noqa: BLE001
            state.add_log(f"Validation failed: {e}")
            log.exception("validation_failed")
        return RedirectResponse("/validation", status_code=303)

    @app.post("/actions/reset-kill-switch")
    async def action_reset_kill(ack: str = Form("")) -> RedirectResponse:
        state = get_app_state()
        try:
            state.risk.clear_kill_switch(operator_ack=ack)
            state.add_log("Kill switch cleared by operator")
        except RiskBreachError as e:
            state.add_log(e.guidance)
        return RedirectResponse("/risk", status_code=303)

    @app.post("/actions/onboarding")
    async def action_onboarding(step: int = Form(0)) -> RedirectResponse:
        state = get_app_state()
        state.onboarding_step = max(0, min(int(step), 4))
        return RedirectResponse("/setup", status_code=303)

    @app.post("/actions/toggle-bot")
    async def action_toggle_bot() -> RedirectResponse:
        state = get_app_state()
        if state.settings.live_trading and not state.settings.is_dry_run:
            state.add_log("Refusing to toggle live bot from UI without ops runbook.")
        else:
            state.bot_running = not state.bot_running
            state.add_log(f"Bot running flag → {state.bot_running} (demo/paper orchestration flag)")
        return RedirectResponse("/", status_code=303)

    # ---- JSON API ----
    @app.get("/api/health")
    async def api_health() -> dict[str, Any]:
        return {"status": "ok", "version": __version__, "disclaimer": ACCURACY_DISCLAIMER}

    @app.get("/api/status")
    async def api_status() -> dict[str, Any]:
        return get_app_state().status_dict()

    @app.get("/api/risk")
    async def api_risk() -> dict[str, Any]:
        return get_app_state().risk_state().to_dict()

    @app.get("/api/news")
    async def api_news() -> dict[str, Any]:
        state = get_app_state()
        return {
            "articles": [a.to_dict() for a in state.articles],
            "errors": state.news.last_errors,
        }

    @app.get("/api/signals")
    async def api_signals() -> dict[str, Any]:
        return {"signals": [s.to_dict() for s in get_app_state().signals]}

    @app.get("/api/validation")
    async def api_validation() -> dict[str, Any]:
        state = get_app_state()
        return state.validation.to_dict() if state.validation else {"status": "not_run"}

    @app.get("/api/guidance")
    async def api_guidance() -> dict[str, Any]:
        return {"guidance": get_app_state().settings.missing_required_guidance()}

    @app.post("/api/news/refresh")
    async def api_news_refresh() -> dict[str, Any]:
        state = get_app_state()
        articles = await state.refresh_news_and_sentiment()
        return {"count": len(articles), "articles": [a.to_dict() for a in articles[:20]]}

    @app.post("/api/validation/run")
    async def api_validation_run() -> dict[str, Any]:
        state = get_app_state()
        df = load_or_download(
            "BTC/USDT",
            state.settings.timeframe,
            state.settings.user_data_dir / "data",
            exchange_id="bybit",
            limit=1000,
        )
        if df.empty:
            return {
                "error": "No OHLCV",
                "guidance": "Public CCXT download failed. Check network; retry make download-data.",
            }
        result = walk_forward_momentum(df["close"])
        state.validation = result
        return result.to_dict()

    return app
