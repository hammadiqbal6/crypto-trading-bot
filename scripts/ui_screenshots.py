#!/usr/bin/env python3
"""Capture dashboard screenshots for docs/PR (desktop + mobile)."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8080"
OUT = Path("docs/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

PAGES = [
    ("/", "overview"),
    ("/setup", "setup"),
    ("/news", "news"),
    ("/validation", "validation"),
    ("/risk", "risk"),
    ("/logs", "logs"),
]


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Desktop
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        for path, name in PAGES:
            page.goto(f"{BASE}{path}", wait_until="networkidle")
            page.screenshot(path=str(OUT / f"{name}-desktop.png"), full_page=True)
            print("shot", name, "desktop")

        # Exercise validation + news actions from overview
        page.goto(f"{BASE}/", wait_until="networkidle")
        # missing-keys banner should be visible
        assert page.locator(".banner.warn, .hero").count() >= 1

        # Mobile
        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.goto(f"{BASE}/", wait_until="networkidle")
        mobile.screenshot(path=str(OUT / "overview-mobile.png"), full_page=True)
        mobile.goto(f"{BASE}/setup", wait_until="networkidle")
        mobile.screenshot(path=str(OUT / "setup-mobile.png"), full_page=True)
        print("shot mobile")

        # Run validation via UI form
        page.goto(f"{BASE}/validation", wait_until="networkidle")
        page.locator('form[action="/actions/run-validation"] button').click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        # may take a bit for download
        for _ in range(30):
            if page.locator(".stat .value").count() > 0 and "Mean OOS" in page.content():
                break
            page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT / "validation-results-desktop.png"), full_page=True)
        print("shot validation results")

        browser.close()
    print("done", OUT)


if __name__ == "__main__":
    main()
