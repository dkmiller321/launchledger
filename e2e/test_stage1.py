"""Stage 1 — Systems."""

from __future__ import annotations

import httpx
import pytest
from playwright.sync_api import Page, expect

from e2e.helpers import tid


@pytest.mark.stage1
def test_e2e_01_record_viewer(page: Page, api: httpx.Client, live_server: str) -> None:
    """E2E-01 record viewer (S2, S6, U2)."""
    serial = api.get("/systems/mes/serials/SN-0042")
    assert serial.status_code == 200
    body = serial.json()
    assert body["status"] == "IN_BUILD"
    assert body["location"] == "Bay 3 - Engine Integration"

    page.goto(f"{live_server}/records/mes/serial/SN-0042")
    view = tid(page, "record-view")
    expect(view).to_have_attribute("data-id", "SN-0042")
    expect(page.locator("[data-testid=record-field][data-field=status]")).to_contain_text(
        "IN_BUILD"
    )


@pytest.mark.stage1
def test_e2e_02_system_apis_and_filters(api: httpx.Client) -> None:
    """E2E-02 system APIs and filters (S1, S3, S4)."""
    open_pos = api.get(
        "/systems/erp/purchase_orders", params={"supplier_id": "SUP-007", "status": "OPEN"}
    ).json()
    assert open_pos["total"] == 2
    assert sorted(item["po_id"] for item in open_pos["items"]) == ["PO-10233", "PO-10240"]

    late = api.get(
        "/systems/erp/purchase_orders", params={"supplier_id": "SUP-007", "late_only": "true"}
    ).json()
    assert [item["po_id"] for item in late["items"]] == ["PO-10233"]

    used = api.get("/systems/plm/parts/P-1077/where_used").json()
    assert sorted(item["parent_pn"] for item in used["items"]) == ["P-2001", "P-2110"]

    missing = api.get("/systems/mes/serials/SN-0404")
    assert missing.status_code == 404
    assert missing.json() == {"error": "not_found"}


@pytest.mark.stage1
def test_e2e_03_deterministic_seed(api: httpx.Client) -> None:
    """E2E-03 deterministic seed (S5)."""
    before = api.get("/api/test/seed-hash").json()["hash"]
    assert api.post("/api/test/reset", timeout=60).status_code == 200
    after = api.get("/api/test/seed-hash").json()["hash"]
    assert before == after

    totals = {
        "/systems/plm/parts": 120,
        "/systems/mes/serials": 300,
        "/systems/mes/work_orders": 400,
        "/systems/erp/purchase_orders": 600,
        "/systems/mes/nonconformances": 80,
        "/systems/erp/suppliers": 25,
    }
    for path, expected in totals.items():
        assert api.get(path, params={"limit": 1}).json()["total"] == expected, path
