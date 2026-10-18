"""Playwright e2e: dashboard pages, banners, validation action."""

from __future__ import annotations

import os
import threading
import time
import urllib.request
from collections.abc import Generator

import pytest
import uvicorn
from playwright.sync_api import sync_playwright

os.environ.setdefault("LIVE_TRADING", "false")
os.environ.setdefault("TRADING_MODE", "demo")
os.environ.setdefault("LLM_PROVIDER", "none")
os.environ.setdefault("USE_FINBERT", "false")

PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"


@pytest.fixture(scope="module")
def server() -> Generator[str, None, None]:
    from crypto_bot.api.app import create_app
    from crypto_bot.config import settings as settings_mod
    from crypto_bot.services import app_state as app_state_mod

    settings_mod.get_settings.cache_clear()
    app_state_mod._STATE = None
    app = create_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        try:
            urllib.request.urlopen(f"{BASE}/api/health", timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)
    yield BASE
    server.should_exit = True


@pytest.mark.e2e
def test_overview_shows_brand_and_guidance(server: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(f"{server}/", wait_until="networkidle")
        assert page.locator(".brand-text").inner_text() == "Signalforge"
        assert page.locator(".banner.warn").is_visible()
        assert "Action needed" in page.content()
        assert "Bybit Demo API keys missing" in page.content()
        browser.close()


@pytest.mark.e2e
def test_all_nav_pages_load(server: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        for path in ("/", "/setup", "/news", "/validation", "/risk", "/logs"):
            page.goto(f"{server}{path}", wait_until="networkidle")
            assert page.locator(".brand-text").is_visible()
            assert "Internal Server Error" not in page.content()
        browser.close()


@pytest.mark.e2e
def test_setup_wizard_advances(server: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{server}/setup", wait_until="networkidle")
        page.locator('form[action="/actions/onboarding"] button').click()
        page.wait_for_load_state("networkidle")
        assert "Current step:" in page.content()
        browser.close()


@pytest.mark.e2e
def test_mobile_viewport_overview(server: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(f"{server}/", wait_until="networkidle")
        assert page.locator(".brand-text").is_visible()
        assert page.locator(".hero h1").inner_text() == "Signalforge"
        browser.close()
