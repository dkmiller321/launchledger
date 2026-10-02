"""Stage 3 — Remaining workflows and guardrails."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from e2e.helpers import M4, M5, M6, ask, tid

RULES = (
    "citation_required",
    "facts_match_source",
    "ids_exist",
    "export_control",
    "uncertainty_stated",
)


def _assert_blocked(page: Page, *fragments: str) -> None:
    expect(tid(page, "decision-badge")).to_have_text("Blocked")
    reason = tid(page, "decision-reason")
    for fragment in fragments:
        expect(reason).to_contain_text(fragment)
    expect(tid(page, "answer-text")).to_have_count(0)
    expect(tid(page, "claim")).to_have_count(0)
    expect(tid(page, "citation")).to_have_count(0)


@pytest.mark.stage3
def test_e2e_11_w4_to_w6(page: Page, live_server: str) -> None:
    """E2E-11 W4–W6 (W4, W5, W6)."""
    ask(page, live_server, M4)
    expect(tid(page, "decision-badge")).to_have_text("Answered")
    expect(tid(page, "workflow-chip")).to_have_text("ncr_summary")
    expect(tid(page, "answer-text")).to_contain_text("NCR-0311")

    ask(page, live_server, M5)
    expect(tid(page, "decision-badge")).to_have_text("Answered")
    expect(tid(page, "workflow-chip")).to_have_text("po_status")
    expect(tid(page, "answer-text")).to_contain_text("late")

    ask(page, live_server, M6)
    expect(tid(page, "decision-badge")).to_have_text("Answered")
    expect(tid(page, "workflow-chip")).to_have_text("build_readiness")
    assert tid(page, "answer-text").inner_text().strip().startswith("No.")


@pytest.mark.stage3
def test_e2e_12_hallucinated_id_blocked(page: Page, live_server: str) -> None:
    """E2E-12 hallucinated ID is blocked (G3, U3)."""
    ask(page, live_server, "ghost serial test")
    _assert_blocked(page, "ids_exist", "SN-9999")

    tid(page, "trace-link").click()
    for rule in RULES:
        result = page.locator(f"[data-testid=guardrail-result][data-rule={rule}]")
        expect(result).to_have_count(1)
        expect(result).to_have_attribute("data-passed", "false" if rule == "ids_exist" else "true")


@pytest.mark.stage3
def test_e2e_13_wrong_value_blocked(page: Page, live_server: str) -> None:
    """E2E-13 wrong value is blocked (G2)."""
    ask(page, live_server, "wrong status test")
    _assert_blocked(page, "facts_match_source", "IN_BUILD", "SHIPPED")


@pytest.mark.stage3
def test_e2e_14_uncited_claim_blocked(page: Page, live_server: str) -> None:
    """E2E-14 uncited claim is blocked (G1)."""
    ask(page, live_server, "uncited claim test")
    _assert_blocked(page, "citation_required")


@pytest.mark.stage3
def test_e2e_15_export_controlled_blocked(page: Page, live_server: str) -> None:
    """E2E-15 export-controlled data is blocked (G4)."""
    ask(page, live_server, "inducer details test")
    _assert_blocked(page, "export_control")
    assert "11.5" not in page.content()


@pytest.mark.stage3
def test_e2e_16_uncertainty_must_be_stated(page: Page, live_server: str) -> None:
    """E2E-16 uncertainty must be stated (G5, G3)."""
    ask(page, live_server, "Where is SN-0404?")
    expect(tid(page, "decision-badge")).to_have_text("Answered")
    expect(tid(page, "caveat")).to_have_count(1)
    expect(tid(page, "caveat")).to_contain_text("SN-0404 was not found in MES.")

    ask(page, live_server, "missing caveat test")
    _assert_blocked(page, "ids_exist", "uncertainty_stated")


@pytest.mark.stage3
def test_e2e_17_output_repair(page: Page, live_server: str) -> None:
    """E2E-17 output repair (A4, reliability)."""
    ask(page, live_server, "repairable output test")
    expect(tid(page, "decision-badge")).to_have_text("Answered")
    tid(page, "trace-link").click()
    expect(page.locator("[data-testid=trace-step][data-repair=true]")).to_have_count(1)

    ask(page, live_server, "malformed output test")
    expect(tid(page, "decision-badge")).to_have_text("Declined")
    expect(tid(page, "decision-reason")).to_have_text(
        "Declined: model output failed validation after 1 repair attempt."
    )
