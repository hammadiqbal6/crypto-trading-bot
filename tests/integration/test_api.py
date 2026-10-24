"""API / dashboard smoke tests."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Safe defaults before import
os.environ.setdefault("LIVE_TRADING", "false")
os.environ.setdefault("TRADING_MODE", "paper")
os.environ.setdefault("LLM_PROVIDER", "none")
os.environ.setdefault("USE_FINBERT", "false")


@pytest.fixture()
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setenv("USE_FINBERT", "false")
    from crypto_bot.api.app import create_app
    from crypto_bot.config import settings as settings_mod
    from crypto_bot.services import app_state as app_state_mod

    settings_mod.get_settings.cache_clear()
    app_state_mod._STATE = None
    app = create_app()
    return TestClient(app)


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_dashboard_renders(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert b"Signalforge" in r.content
    assert b"Action needed" in r.content or b"Overview" in r.content


def test_setup_and_pages(client: TestClient) -> None:
    for path in ("/setup", "/news", "/validation", "/risk", "/logs"):
        r = client.get(path)
        assert r.status_code == 200, path


def test_status_json(client: TestClient) -> None:
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert body["dry_run"] is True
    assert "accuracy_disclaimer" in body
