"""Stage 5 — Drift. E2E-21 is the most important test in the suite."""

from __future__ import annotations

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect

from e2e.helpers import (
    M1,
    M2,
    M5,
    ask,
    drift_toggle,
    resolve_open_incident,
    run_json,
    run_mock_evals,
    tid,
)


def _system_status(page: Page, system: str) -> Locator:
    return page.locator(f"[data-testid=drift-system-status][data-system={system}]")


@pytest.mark.stage5
def test_e2e_20_no_false_positives(page: Page, live_server: str) -> None:
    """E2E-20 no false positives (D3, D6)."""
    page.goto(f"{live_server}/drift")
    statuses = tid(page, "drift-system-status")
    assert statuses.count() >= 3
    for i in range(statuses.count()):
        expect(statuses.nth(i)).to_have_attribute("data-status", "green")

    with page.expect_response(lambda r: r.request.method == "POST"):
        tid(page, "drift-check-now").click()
    page.goto(f"{live_server}/drift")
    statuses = tid(page, "drift-system-status")
    for i in range(statuses.count()):
        expect(statuses.nth(i)).to_have_attribute("data-status", "green")
    expect(tid(page, "incident-row")).to_have_count(0)


@pytest.mark.stage5
def test_e2e_21_rename_declined_never_wrong(
    page: Page, api: httpx.Client, live_server: str
) -> None:
    """E2E-21 MOST IMPORTANT — silent upstream rename is declined, never answered wrong."""
    # 1. Baseline.
    ask(page, live_server, M2)
    expect(tid(page, "decision-badge")).to_have_text("Answered")

    # 2. Inject the rename.
    drift_toggle(page, live_server, "erp_rename_promised_date", on=True)

    # 3. Same question is declined.
    run_id = ask(page, live_server, M2)
    expect(tid(page, "decision-badge")).to_have_text("Declined")
    reason = tid(page, "decision-reason")
    expect(reason).to_contain_text("ERP")
    expect(reason).to_contain_text("promised_date")
    expect(tid(page, "answer-text")).to_have_count(0)
    run = run_json(api, run_id)
    assert any(
        step.get("contract") == "fail" and "/purchase_orders" in str(step.get("endpoint", ""))
        for step in run["steps"]
    ), run["steps"]

    # 4. Incident on /drift.
    page.goto(f"{live_server}/drift")
    incident = page.locator("[data-testid=incident-row][data-system=erp][data-field=promised_date]")
    expect(incident).to_have_count(1)
    expect(incident).to_have_attribute("data-kind", "shape")
    expect(incident).to_have_attribute("data-status", "open")
    expect(incident.get_by_test_id("incident-runs-affected")).to_have_text("1")
    expect(_system_status(page, "erp")).to_have_attribute("data-status", "red")
    expect(_system_status(page, "plm")).to_have_attribute("data-status", "green")
    expect(_system_status(page, "mes")).to_have_attribute("data-status", "green")

    # 5. Drift-mode eval: zero wrong answers, at least one declined.
    run_mock_evals(page, live_server, drift="erp_rename_promised_date")
    expect(tid(page, "eval-wrong-count")).to_have_text("0")
    declined = int(tid(page, "eval-declined-count").inner_text().strip())
    assert declined >= 1
    page.goto(f"{live_server}/drift")
    expect(
        page.locator("[data-testid=drift-scenario-toggle][data-scenario=erp_rename_promised_date]")
    ).to_be_checked()

    # 6. Disable + resolve, then answered again.
    drift_toggle(page, live_server, "erp_rename_promised_date", on=False)
    resolve_open_incident(page, live_server)
    page.goto(f"{live_server}/")
    ask(page, live_server, M2)
    expect(tid(page, "decision-badge")).to_have_text("Answered")
    expect(tid(page, "answer-text")).to_contain_text("PO-10233")


@pytest.mark.stage5
def test_e2e_22_new_enum_value_declined(page: Page, live_server: str) -> None:
    """E2E-22 new enum value is declined (D2, D5)."""
    drift_toggle(page, live_server, "mes_new_wo_status", on=True)
    page.goto(f"{live_server}/")
    ask(page, live_server, M1)
    expect(tid(page, "decision-badge")).to_have_text("Declined")
    reason = tid(page, "decision-reason")
    for fragment in ("MES", "status", "HOLD_QA"):
        expect(reason).to_contain_text(fragment)

    page.goto(f"{live_server}/drift")
    expect(page.locator("[data-testid=incident-row][data-kind=enum]")).to_have_count(1)


@pytest.mark.stage5
def test_e2e_23_unit_change_monitor_then_gate(page: Page, live_server: str) -> None:
    """E2E-23 unit change is caught by the monitor, then gated (D3, D4, D5)."""
    drift_toggle(page, live_server, "erp_cost_in_cents", on=True)
    page.goto(f"{live_server}/")
    ask(page, live_server, M5)
    expect(tid(page, "decision-badge")).to_have_text("Answered")

    page.goto(f"{live_server}/drift")
    with page.expect_response(lambda r: r.request.method == "POST"):
        tid(page, "drift-check-now").click()
    page.goto(f"{live_server}/drift")
    incident = page.locator("[data-testid=incident-row][data-system=erp][data-field=unit_cost_usd]")
    expect(incident).to_have_count(1)
    expect(incident).to_have_attribute("data-kind", "distribution")

    page.goto(f"{live_server}/")
    ask(page, live_server, M5)
    expect(tid(page, "decision-badge")).to_have_text("Declined")
    expect(tid(page, "decision-reason")).to_contain_text("open drift incident")
    expect(tid(page, "decision-reason")).to_contain_text("unit_cost_usd")

    drift_toggle(page, live_server, "erp_cost_in_cents", on=False)
    resolve_open_incident(page, live_server)
    page.goto(f"{live_server}/")
    ask(page, live_server, M5)
    expect(tid(page, "decision-badge")).to_have_text("Answered")
