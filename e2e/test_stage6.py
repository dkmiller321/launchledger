"""Stage 6 — Feedback (P1)."""

from __future__ import annotations

import pytest
from playwright.sync_api import Locator, Page, expect

from e2e.helpers import M1, ask, run_mock_evals, tid


def _thumbs_down(page: Page, live_server: str) -> None:
    ask(page, live_server, M1)
    tid(page, "feedback-down").click()
    expect(tid(page, "feedback-submit")).to_be_disabled()
    tid(page, "feedback-reason").select_option("wrong_data")
    tid(page, "feedback-text").fill("Location looks stale")
    expect(tid(page, "feedback-submit")).to_be_enabled()
    tid(page, "feedback-submit").click()
    expect(tid(page, "feedback-thanks")).to_be_visible()


def _only_row(page: Page, live_server: str) -> Locator:
    page.goto(f"{live_server}/feedback")
    rows = tid(page, "feedback-row")
    expect(rows).to_have_count(1)
    return rows.first


def _triage(page: Page, row: Locator, status: str, disposition: str | None = None) -> None:
    row.get_by_test_id("feedback-status-select").select_option(status)
    if disposition:
        row.get_by_test_id("feedback-disposition-select").select_option(disposition)
    with page.expect_response(lambda r: r.request.method == "POST"):
        row.get_by_test_id("feedback-save").click()
    expect(page.locator(f"[data-testid=feedback-row][data-status={status}]")).to_have_count(1)


@pytest.mark.stage6
def test_e2e_24_thumbs_down_creates_item(page: Page, live_server: str) -> None:
    """E2E-24 thumbs-down creates a triage item (F1, U8)."""
    _thumbs_down(page, live_server)
    row = _only_row(page, live_server)
    expect(row).to_have_attribute("data-status", "new")
    expect(row).to_contain_text("Wrong data")
    expect(row).to_contain_text("Location looks stale")


@pytest.mark.stage6
def test_e2e_25_triage_flow_logged(page: Page, live_server: str) -> None:
    """E2E-25 triage flow is logged and persists (F2, U9)."""
    _thumbs_down(page, live_server)
    row = _only_row(page, live_server)
    _triage(page, row, "triaged", "data_issue")
    _triage(page, tid(page, "feedback-row").first, "fixed")
    _triage(page, tid(page, "feedback-row").first, "verified")
    expect(tid(page, "feedback-event")).to_have_count(3)

    page.reload()
    row = tid(page, "feedback-row").first
    expect(row).to_have_attribute("data-status", "verified")
    expect(tid(page, "feedback-event")).to_have_count(3)
    expect(row.get_by_test_id("feedback-disposition-select")).to_have_value("data_issue")


@pytest.mark.stage6
def test_e2e_26_feedback_becomes_case(page: Page, live_server: str) -> None:
    """E2E-26 feedback becomes a regression case (F3, U9)."""
    _thumbs_down(page, live_server)
    row = _only_row(page, live_server)
    feedback_id = row.get_attribute("data-feedback-id")
    assert feedback_id
    case_id = f"draft-{feedback_id}"

    row.get_by_test_id("feedback-convert").click()
    expect(tid(page, "feedback-convert-result")).to_contain_text(case_id)

    run_mock_evals(page, live_server, drift="none")
    draft = page.locator(f"[data-testid=eval-case-row][data-case-id='{case_id}']")
    expect(draft).to_have_count(1)
    expect(draft).to_have_attribute("data-passed", "true")
    expect(tid(page, "eval-pass-count")).to_have_text("30/30")
