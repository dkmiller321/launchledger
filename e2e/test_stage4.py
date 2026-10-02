"""Stage 4 — Evals."""

from __future__ import annotations

import httpx
import pytest
from playwright.sync_api import Page, expect

from e2e.helpers import run_mock_evals, suite_total, tid


@pytest.mark.stage4
def test_e2e_18_mock_eval_suite(page: Page, api: httpx.Client, live_server: str) -> None:
    """E2E-18 mock eval suite (V1–V3, V6, U4)."""
    eval_id = run_mock_evals(page, live_server, drift="none")
    total = suite_total(api, eval_id)
    expect(tid(page, "eval-pass-count")).to_have_text(f"{total}/{total}")
    rates = tid(page, "eval-pass-rate")
    expect(rates).to_have_count(total // 5)
    for i in range(total // 5):
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

    eval_id = run_mock_evals(page, live_server, drift="none")
    total = suite_total(api, eval_id)
    expect(tid(page, "eval-pass-count")).to_have_text(f"{total - 1}/{total}")
    row = page.locator("[data-testid=eval-case-row][data-case-id=W5-01]")
    expect(row).to_have_attribute("data-passed", "false")
    diff = row.get_by_test_id("eval-case-diff")
    expect(diff).to_contain_text("CLOSED")
    expect(diff).to_contain_text("OPEN")
