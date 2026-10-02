"""Stage 7 — P1 systems and workflows."""

from __future__ import annotations

import httpx
import pytest
from playwright.sync_api import Page, expect

from e2e.helpers import M5, ask, drift_toggle, run_mock_evals, tid

P1_CASES = [
    ("Trace requirement REQ-118", "requirement_trace", ["P-1077", "NCR-0311"], []),
    (
        "What's the impact of moving P-1077 to rev D?",
        "revision_impact",
        ["SN-0042", "SN-0057", "WO-50103", "WO-50217"],
        [],
    ),
    (
        "Show the scorecard for Apex Castings",
        "supplier_scorecard",
        ["Apex Castings", "PO-10233", "on-time"],
        [],
    ),
    ("What's the cycle time for P-2001?", "cycle_time", ["days"], []),
    ("Shortage report for P-1077", "shortage_report", ["P-1077", "PO-10233"], []),
    (
        "Which export-controlled parts are in P-2001?",
        "export_check",
        ["P-1077", "P-2001"],
        ["11.5"],
    ),
]
REVISION_IMPACT_Q = P1_CASES[1][0]


@pytest.mark.stage7
def test_e2e_27_p1_workflows(page: Page, live_server: str) -> None:
    """E2E-27 P1 workflows (W7–W12, S7, S8)."""
    for question, chip, must_contain, must_not_contain in P1_CASES:
        ask(page, live_server, question)
        expect(tid(page, "decision-badge")).to_have_text("Answered")
        expect(tid(page, "workflow-chip")).to_have_text(chip)
        answer = tid(page, "answer-text")
        for text in must_contain:
            expect(answer).to_contain_text(text)
        for text in must_not_contain:
            expect(answer).not_to_contain_text(text)


@pytest.mark.stage7
def test_e2e_28_p1_drift_scenarios(page: Page, api: httpx.Client, live_server: str) -> None:
    """E2E-28 P1 drift scenarios (D7)."""
    drift_toggle(page, live_server, "plm_null_revision", on=True)
    page.goto(f"{live_server}/")
    ask(page, live_server, REVISION_IMPACT_Q)
    expect(tid(page, "decision-badge")).to_have_text("Declined")
    expect(tid(page, "decision-reason")).to_contain_text("PLM")
    expect(tid(page, "decision-reason")).to_contain_text("revision")

    assert api.post("/api/test/reset", timeout=60).status_code == 200

    drift_toggle(page, live_server, "erp_date_format", on=True)
    page.goto(f"{live_server}/")
    ask(page, live_server, M5)
    expect(tid(page, "decision-badge")).to_have_text("Declined")
    expect(tid(page, "decision-reason")).to_contain_text("ERP")
    expect(tid(page, "decision-reason")).to_contain_text("due_date")


@pytest.mark.stage7
def test_e2e_29_full_mock_suite(page: Page, live_server: str) -> None:
    """E2E-29 full mock suite (V7)."""
    run_mock_evals(page, live_server, drift="none")
    expect(tid(page, "eval-pass-count")).to_have_text("60/60")
    rates = tid(page, "eval-pass-rate")
    expect(rates).to_have_count(12)
    for i in range(12):
        expect(rates.nth(i)).to_have_text("5/5")
