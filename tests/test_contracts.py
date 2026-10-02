"""IT-08: contracts, drift transforms and the distribution monitor."""

from typing import Any

from starlette.testclient import TestClient

from launchledger.contracts.check import OpenIncident, check_response, validate_records
from launchledger.contracts.monitor import distribution_shift
from launchledger.drift.scenarios import SCENARIOS

PO = {
    "po_id": "PO-10233",
    "supplier_id": "SUP-007",
    "part_number": "P-1077",
    "qty": 4,
    "due_date": "2026-09-15",
    "promised_date": "2026-10-20",
    "status": "OPEN",
    "unit_cost_usd": 18450.0,
    "received_on": None,
}
WO = {
    "wo_id": "WO-50103",
    "serial_number": "SN-0042",
    "status": "OPEN",
    "blocked_reason": None,
    "depends_on_po": None,
    "description": "Final assembly",
    "opened_on": "2026-09-01",
    "closed_on": None,
}
PART = {
    "part_number": "P-2110",
    "name": "Fuel turbopump assembly",
    "revision": "B",
    "mass_kg": 88.0,
    "unit_cost_usd": 398000.0,
    "export_controlled": True,
    "controlled_notes": "Impeller balance grade G1.0",
}


def problems(record_type: str, rec: dict[str, Any]) -> list[str]:
    return [v.problem for v in validate_records(record_type, [rec])]


def test_clean_records_pass() -> None:
    assert problems("purchase_order", PO) == []
    assert problems("work_order", WO) == []
    assert problems("part", PART) == []


def test_each_scenario_breaks_its_contract_on_the_expected_field() -> None:
    def apply(name: str, rec: dict[str, Any]) -> dict[str, Any]:
        return SCENARIOS[name].transform(rec)

    assert problems("purchase_order", apply("erp_rename_promised_date", PO)) == [
        "promised_date missing",
        "unexpected field promise_date",
    ]
    assert problems("work_order", apply("mes_new_wo_status", WO)) == [
        "status unexpected value HOLD_QA"
    ]
    assert problems("part", apply("plm_null_revision", PART)) == ["revision is null"]
    us_dates = problems("purchase_order", apply("erp_date_format", PO))
    assert us_dates[0].startswith("due_date invalid date '09/15/2026'")
    # The x100 unit change stays inside the contract on purpose: only the monitor sees it.
    assert problems("purchase_order", apply("erp_cost_in_cents", PO)) == []


def test_rename_decline_reason_template() -> None:
    bad = SCENARIOS["erp_rename_promised_date"].transform(PO)
    result = check_response("erp", "/purchase_orders", "purchase_order", {"items": [bad]}, True, [])
    assert result.decision_reason() == (
        "Declined: upstream data from ERP failed its contract (/purchase_orders: "
        "promised_date missing; unexpected field promise_date)."
    )


def test_open_incident_gates_responses_with_its_field() -> None:
    gate = OpenIncident(1, "erp", "unit_cost_usd", "distribution")
    result = check_response("erp", "/purchase_orders/{po_id}", "purchase_order", PO, False, [gate])
    assert not result.passed
    assert result.decision_reason() == (
        "Declined: open drift incident on ERP unit_cost_usd (distribution)."
    )
    supplier = check_response(
        "erp",
        "/suppliers/{supplier_id}",
        "supplier",
        {"supplier_id": "SUP-007", "name": "Apex Castings"},
        False,
        [gate],
    )
    assert supplier.passed


def test_distribution_shift() -> None:
    assert distribution_shift(100.0, [90.0, 100.0, 120.0]) is None
    assert distribution_shift(100.0, [9000.0, 10000.0, 12000.0]) is not None


def test_clean_monitor_pass_opens_no_incident(clean: None, client: TestClient) -> None:
    from launchledger.contracts.monitor import check_now

    assert check_now() == 0
    assert client.get("/api/drift/incidents").json() == []
