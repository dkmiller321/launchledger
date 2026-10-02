"""Stage 2 — Assistant core."""

from __future__ import annotations

import httpx
import pytest
from playwright.sync_api import Page, expect

from e2e.helpers import M1, M2, M3, M5, ask, run_json, tid


@pytest.mark.stage2
def test_e2e_04_grounded_answer(page: Page, live_server: str) -> None:
    """E2E-04 grounded answer (A1, A4, A5, W1, U1, U2)."""
    page.goto(f"{live_server}/")
    page.evaluate(
        """() => {
            window.__sawPending = false;
            const check = () => {
                const el = document.querySelector('[data-testid=run-pending]');
                if (el) {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    if (style.display !== 'none' && style.visibility !== 'hidden'
                        && rect.width > 0 && rect.height > 0) {
                        window.__sawPending = true;
                    }
                }
            };
            new MutationObserver(check).observe(document.body, {
                subtree: true, childList: true, attributes: true,
            });
            window.__pendingTimer = setInterval(check, 20);
        }"""
    )
    tid(page, "workflow-select").select_option("auto")
    tid(page, "ask-input").fill(M1)
    tid(page, "ask-submit").click()
    page.wait_for_function(
        "() => { const c = document.querySelector('[data-testid=answer-card]');"
        " return !!c && !!c.getAttribute('data-run-id'); }"
    )
    assert page.evaluate("() => window.__sawPending") is True

    expect(tid(page, "decision-badge")).to_have_text("Answered")
    expect(tid(page, "workflow-chip")).to_have_text("serial_status")
    answer = tid(page, "answer-text")
    expect(answer).to_contain_text("WO-50102")
    expect(answer).to_contain_text("PO-10233")
    expect(tid(page, "claim")).to_have_count(3)
    expect(tid(page, "citation")).to_have_count(6)

    citation = page.locator(
        "[data-testid=citation][data-field=status][href$='/records/mes/work_order/WO-50102']"
    )
    citation.first.click()
    expect(page.locator("[data-testid=record-field][data-field=status]")).to_contain_text("BLOCKED")


@pytest.mark.stage2
def test_e2e_05_trace(page: Page, api: httpx.Client, live_server: str) -> None:
    """E2E-05 trace (T1, T2, U7)."""
    run_id = ask(page, live_server, M1)
    tid(page, "trace-link").click()

    expect(page.locator("[data-testid=trace-step][data-kind=llm]")).to_have_count(4)
    expect(
        page.locator("[data-testid=trace-step][data-kind=llm][data-purpose=router]")
    ).to_have_count(1)
    tools = page.locator("[data-testid=trace-step][data-kind=tool]")
    expect(tools).to_have_count(2)
    expect(tools.first).to_contain_text("/systems/mes/serials/SN-0042")

    run = run_json(api, run_id)
    assert run["model"] == "mock/workflow"
    assert run["workflow_source"] == "router"
    assert run["decision"] == "answered"

    page.goto(f"{live_server}/runs")
    row = page.locator(f"[data-testid=run-row][data-run-id='{run_id}']")
    expect(row).to_have_count(1)
    expect(row).to_have_attribute("data-decision", "answered")


@pytest.mark.stage2
def test_e2e_06_manual_workflow_override(page: Page, api: httpx.Client, live_server: str) -> None:
    """E2E-06 manual workflow override (A1)."""
    run_id = ask(page, live_server, M5, workflow="po_status")
    expect(tid(page, "workflow-chip")).to_have_text("po_status (manual)")

    run = run_json(api, run_id)
    assert run["workflow_source"] == "manual"
    assert not [step for step in run["steps"] if step.get("purpose") == "router"]


@pytest.mark.stage2
def test_e2e_07_supplier_impact(page: Page, api: httpx.Client, live_server: str) -> None:
    """E2E-07 supplier impact (W2)."""
    run_id = ask(page, live_server, M2)
    expect(tid(page, "decision-badge")).to_have_text("Answered")
    expect(tid(page, "workflow-chip")).to_have_text("supplier_impact")
    answer = tid(page, "answer-text")
    for text in ("WO-50102", "WO-50217", "PO-10233"):
        expect(answer).to_contain_text(text)

    run = run_json(api, run_id)
    assert len([step for step in run["steps"] if step["kind"] == "tool"]) == 3


@pytest.mark.stage2
def test_e2e_08_where_used(page: Page, live_server: str) -> None:
    """E2E-08 where used (W3)."""
    ask(page, live_server, M3)
    expect(tid(page, "decision-badge")).to_have_text("Answered")
    expect(tid(page, "workflow-chip")).to_have_text("where_used")
    expect(tid(page, "answer-text")).to_contain_text("P-2001")
    expect(tid(page, "answer-text")).to_contain_text("P-2110")


@pytest.mark.stage2
def test_e2e_09_unsupported_question(page: Page, live_server: str) -> None:
    """E2E-09 unsupported question (A5, U3)."""
    ask(page, live_server, "What's the weather in Seattle?")
    expect(tid(page, "decision-badge")).to_have_text("Declined")
    expect(tid(page, "decision-reason")).to_have_text(
        "Declined: no workflow matches this question."
    )
    expect(tid(page, "answer-text")).to_have_count(0)


@pytest.mark.stage2
def test_e2e_10_persistence(page: Page, live_server: str) -> None:
    """E2E-10 persistence (T2)."""
    run_id = ask(page, live_server, M1)
    row_selector = f"[data-testid=run-row][data-run-id='{run_id}']"

    page.goto(f"{live_server}/runs")
    page.reload()
    expect(page.locator(row_selector)).to_have_count(1)

    page.goto(f"{live_server}/runs/{run_id}")
    steps_before = tid(page, "trace-step").count()
    assert steps_before > 0
    answer_before = tid(page, "answer-text").inner_text()
    page.reload()
    expect(tid(page, "trace-step")).to_have_count(steps_before)
    expect(tid(page, "answer-text")).to_have_text(answer_before)

    page.goto(f"{live_server}/runs")
    tid(page, "runs-filter-decision").select_option("declined")
    expect(page.locator(row_selector)).to_have_count(0)
    tid(page, "runs-filter-decision").select_option("answered")
    expect(page.locator(row_selector)).to_have_count(1)
