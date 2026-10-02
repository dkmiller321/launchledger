"""Stage 4 — Evals."""

from __future__ import annotations

import httpx
import pytest
from playwright.sync_api import Page, expect

from e2e.helpers import run_mock_evals, tid


@pytest.mark.stage4
def test_e2e_18_mock_eval_suite(page: Page, live_server: str) -> None:
    """E2E-18 mock eval suite (V1–V3, V6, U4)."""
    run_mock_evals(page, live_server, drift="none")
    expect(tid(page, "eval-pass-count")).to_have_text("30/30")
    rates = tid(page, "eval-pass-rate")
    expect(rates).to_have_count(6)
    for i in range(6):
        expect(rates.nth(i)).to_have_text("5/5")


@pytest.mark.stage4
def test_e2e_19_failing_case_diff(page: Page, api: httpx.Client, live_server: str) -> None:
    """E2E-19 failing case shows its diff (V2, V6)."""
    override = api.post(
        "/api/test/eval-overrides",
        json={
            "case_id": "W5-01",
            "expected_facts": [
                {
                    "system": "ERP",
                    "record_type": "purchase_order",
                    "record_id": "PO-10233",
                    "field": "status",
                    "value": "CLOSED",
                }
            ],
        },
    )
    assert override.status_code == 200

    run_mock_evals(page, live_server, drift="none")
    expect(tid(page, "eval-pass-count")).to_have_text("29/30")
    row = page.locator("[data-testid=eval-case-row][data-case-id=W5-01]")
    expect(row).to_have_attribute("data-passed", "false")
    diff = row.get_by_test_id("eval-case-diff")
    expect(diff).to_contain_text("CLOSED")
    expect(diff).to_contain_text("OPEN")
