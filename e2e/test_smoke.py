"""Smoke — real model (manual only, never in CI). The server must run with LLM_MODE=openrouter."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

from e2e.helpers import M1, M2, ask, drift_toggle, tid

REPO_ROOT = Path(__file__).resolve().parent.parent
SMOKE_TIMEOUT_MS = 90_000

pytestmark = pytest.mark.skipif(
    not (os.environ.get("RUN_SMOKE") == "1" and os.environ.get("OPENROUTER_API_KEY")),
    reason="smoke tests need RUN_SMOKE=1 and OPENROUTER_API_KEY",
)


@pytest.fixture(autouse=True)
def _smoke_timeouts(page: Page) -> None:
    page.set_default_timeout(SMOKE_TIMEOUT_MS)
    expect.set_options(timeout=SMOKE_TIMEOUT_MS)


@pytest.mark.smoke
def test_smoke_1_grounded_answer(page: Page, live_server: str) -> None:
    """SMOKE-1 grounded answer."""
    ask(page, live_server, M1)
    expect(tid(page, "decision-badge")).to_have_text("Answered")
    expect(tid(page, "answer-text")).to_contain_text("WO-50102")
    tid(page, "trace-link").click()
    results = tid(page, "guardrail-result")
    assert results.count() > 0
    for i in range(results.count()):
        expect(results.nth(i)).to_have_attribute("data-passed", "true")


@pytest.mark.smoke
def test_smoke_2_router(page: Page, live_server: str) -> None:
    """SMOKE-2 router."""
    ask(page, live_server, "Is PO-10233 late?")
    expect(tid(page, "workflow-chip")).to_have_text("po_status")


@pytest.mark.smoke
def test_smoke_3_drift_beats_real_model(page: Page, live_server: str) -> None:
    """SMOKE-3 drift beats the real model."""
    drift_toggle(page, live_server, "erp_rename_promised_date", on=True)
    try:
        page.goto(f"{live_server}/")
        ask(page, live_server, M2)
        expect(tid(page, "decision-badge")).to_have_text("Declined")
        expect(tid(page, "decision-reason")).to_contain_text("promised_date")
    finally:
        drift_toggle(page, live_server, "erp_rename_promised_date", on=False)
        httpx.get(f"{live_server}/healthz", timeout=10)


@pytest.mark.smoke
def test_smoke_4_real_model_eval_runs(tmp_path: Path) -> None:
    """SMOKE-4 real-model eval runs."""
    model = os.environ.get("WORKFLOW_MODEL")
    assert model, "WORKFLOW_MODEL must be set"
    report = tmp_path / "report.json"
    result = subprocess.run(
        [
            "uv",
            "run",
            "ll",
            "eval",
            "run",
            "--model",
            model,
            "--workflow",
            "W1",
            "--json-out",
            str(report),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    assert json.loads(report.read_text(encoding="utf-8"))["total"] == 5
    output = result.stdout.lower()
    assert "tokens" in output
    assert "cost" in output
