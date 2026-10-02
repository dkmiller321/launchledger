"""Helpers shared by the E2E specs (E2E_TESTS.md §1.9)."""

from __future__ import annotations

from typing import Any

import httpx
from playwright.sync_api import Locator, Page, expect

M1 = "Where is SN-0042 and what's blocking it?"
M2 = "Which open work orders are at risk from late POs from Apex Castings?"
M3 = "Which assemblies use part P-1077?"
M4 = "What open nonconformances are there against SN-0042?"
M5 = "What's the status of PO-10233 and is it late?"
M6 = "Is SN-0042 ready for stage integration?"


def tid(page: Page, name: str) -> Locator:
    return page.get_by_test_id(name)


def _current_run_id(page: Page) -> str | None:
    card = page.locator("[data-testid=answer-card]")
    if card.count() == 0:
        return None
    return card.first.get_attribute("data-run-id")


def ask(page: Page, base_url: str, question: str, workflow: str = "auto") -> str:
    """Submit a question on the ask page and wait for a new answer card; return its run id."""
    if tid(page, "ask-input").count() == 0:
        page.goto(f"{base_url}/")
    previous = _current_run_id(page)
    tid(page, "workflow-select").select_option(workflow)
    tid(page, "ask-input").fill(question)
    tid(page, "ask-submit").click()
    page.wait_for_function(
        """(prev) => {
            const card = document.querySelector('[data-testid=answer-card]');
            if (!card) return false;
            const id = card.getAttribute('data-run-id');
            return !!id && id !== prev;
        }""",
        arg=previous,
    )
    run_id = _current_run_id(page)
    assert run_id
    return run_id


def run_json(api: httpx.Client, run_id: str) -> dict[str, Any]:
    response = api.get(f"/api/runs/{run_id}")
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return data


def drift_toggle(page: Page, base_url: str, scenario: str, on: bool) -> None:
    page.goto(f"{base_url}/drift")
    toggle = page.locator(f"[data-testid=drift-scenario-toggle][data-scenario={scenario}]")
    if toggle.is_checked() != on:
        with page.expect_response(lambda r: "/drift" in r.url and r.request.method == "POST"):
            toggle.click()
    # Reload to prove the state persisted server-side.
    page.goto(f"{base_url}/drift")
    toggle = page.locator(f"[data-testid=drift-scenario-toggle][data-scenario={scenario}]")
    if on:
        expect(toggle).to_be_checked()
    else:
        expect(toggle).not_to_be_checked()


def run_mock_evals(page: Page, base_url: str, drift: str = "none", timeout_ms: int = 90000) -> str:
    """Run the mock eval suite from /evals and wait for it to complete; return the eval id."""
    page.goto(f"{base_url}/evals")
    tid(page, "evals-drift-select").select_option(drift)
    tid(page, "evals-run-mock").click()
    expect(tid(page, "eval-status")).to_have_text("complete", timeout=timeout_ms)
    holder = page.locator("[data-eval-id]:has([data-testid=eval-status])").first
    eval_id = holder.get_attribute("data-eval-id")
    assert eval_id
    return eval_id


def resolve_open_incident(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/drift")
    row = page.locator("[data-testid=incident-row][data-status=open]").first
    row.get_by_test_id("incident-resolve").click()
    expect(page.locator("[data-testid=incident-row][data-status=open]")).to_have_count(0)


def suite_total(api: httpx.Client, eval_id: str) -> int:
    """Golden cases counted by this eval run (30 P0 before stage 7, 60 after; DECISIONS D15)."""
    total = int(api.get(f"/api/evals/{eval_id}").json()["total"])
    assert total >= 30, "the P0 golden cases must always be in the suite"
    return total
