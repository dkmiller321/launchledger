"""Stage 0 — Skeleton."""

from __future__ import annotations

import httpx
import pytest
from playwright.sync_api import Page, expect

from e2e.helpers import tid


@pytest.mark.stage0
def test_e2e_00_app_boots(page: Page, api: httpx.Client, live_server: str) -> None:
    """E2E-00 app boots."""
    health = api.get("/healthz")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "db": True, "llm_mode": "mock"}

    page.goto(f"{live_server}/")
    for name in ("ask-input", "ask-submit", "workflow-select"):
        expect(tid(page, name)).to_be_visible()
    for nav in ("ask", "runs", "evals", "drift", "feedback", "dashboard"):
        expect(tid(page, f"nav-{nav}")).to_be_visible()

    reset = api.post("/api/test/reset", timeout=60)
    assert reset.status_code == 200
    assert reset.json() == {"ok": True}
