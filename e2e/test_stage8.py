"""Stage 8 — Dashboard (P1)."""

from __future__ import annotations

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect


def _cell(page: Page, panel: str, key: str) -> Locator:
    return page.locator(
        f"[data-testid=dash-panel][data-panel={panel}] [data-testid=dash-table] [data-key='{key}']"
    )


@pytest.mark.stage8
def test_e2e_30_dashboard_numbers(page: Page, api: httpx.Client, live_server: str) -> None:
    """E2E-30 dashboard numbers (B1, U10)."""
    assert api.post("/api/test/seed-activity", timeout=60).status_code == 200

    page.goto(f"{live_server}/dashboard")
    for panel in ("inflow-outflow", "backlog", "eval-pass-rate", "drift-incidents", "decision-mix"):
        expect(page.locator(f"[data-testid=dash-panel][data-panel={panel}]")).to_have_count(1)

    for key, value in (("answered", "14"), ("declined", "4"), ("blocked", "2")):
        expect(_cell(page, "decision-mix", key)).to_have_text(value)
    for key, value in (("new", "1"), ("triaged", "2"), ("fixed", "1")):
        expect(_cell(page, "backlog", key)).to_have_text(value)
    expect(_cell(page, "inflow-outflow", "inflow-2026-W39")).to_have_text("3")
    expect(_cell(page, "inflow-outflow", "outflow-2026-W39")).to_have_text("3")
    expect(_cell(page, "eval-pass-rate", "latest")).to_have_text("30/30")
    expect(_cell(page, "drift-incidents", "total")).to_have_text("2")
