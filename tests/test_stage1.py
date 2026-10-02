"""IT-03: deterministic seed, totals and pinned records (E2E_TESTS.md §1.4)."""

from sqlalchemy import func, select
from starlette.testclient import TestClient

from launchledger.db import models as m
from launchledger.db.session import session_scope
from launchledger.systems.apps import is_late
from launchledger.systems.seed import (
    NCRS,
    PARTS,
    PURCHASE_ORDERS,
    SERIALS,
    TOTALS,
    WORK_ORDERS,
    build_rows,
    seed_hash,
)


def test_build_rows_is_deterministic() -> None:
    assert build_rows() == build_rows()


def test_it_03_seed_hash_is_stable_and_totals_match(clean: None) -> None:
    from launchledger.ops import seed_systems

    with session_scope() as s:
        first = seed_hash(s)
    seed_systems()
    with session_scope() as s:
        assert seed_hash(s) == first
        for table, model in [
            ("parts", m.Part),
            ("bom_lines", m.BomLine),
            ("serials", m.Serial),
            ("work_orders", m.WorkOrder),
            ("inspections", m.Inspection),
            ("nonconformances", m.Nonconformance),
            ("suppliers", m.Supplier),
            ("purchase_orders", m.PurchaseOrder),
        ]:
            assert s.scalar(select(func.count()).select_from(model)) == TOTALS[table], table


def test_it_03_pinned_records_exact(clean: None, client: TestClient) -> None:
    for pn, name, rev, mass, cost, ctrl, notes in PARTS:
        got = client.get(f"/systems/plm/parts/{pn}").json()
        assert got == {
            "part_number": pn,
            "name": name,
            "revision": rev,
            "mass_kg": mass,
            "unit_cost_usd": cost,
            "export_controlled": ctrl,
            "controlled_notes": notes,
        }
    for sn, pn, rev, status, loc in SERIALS:
        got = client.get(f"/systems/mes/serials/{sn}").json()
        assert (got["part_number"], got["revision"], got["status"], got["location"]) == (
            pn,
            rev,
            status,
            loc,
        )
    for wo, sn, status, reason, po, desc, *_ in WORK_ORDERS:
        got = client.get(f"/systems/mes/work_orders/{wo}").json()
        assert (
            got["serial_number"],
            got["status"],
            got["blocked_reason"],
            got["depends_on_po"],
            got["description"],
        ) == (sn, status, reason, po, desc)
    for ncr, sn, sev, status, req, desc in NCRS:
        got = client.get(f"/systems/mes/nonconformances/{ncr}").json()
        assert (
            got["serial_number"],
            got["severity"],
            got["status"],
            got["requirement_id"],
            got["description"],
        ) == (sn, sev, status, req, desc)
    for po, sup, pn, qty, due, prom, status, cost, _ in PURCHASE_ORDERS:
        got = client.get(f"/systems/erp/purchase_orders/{po}").json()
        assert (
            got["supplier_id"],
            got["part_number"],
            got["qty"],
            got["due_date"],
            got["promised_date"],
            got["status"],
            got["unit_cost_usd"],
        ) == (sup, pn, qty, due.isoformat(), prom.isoformat(), status, cost)
    apex = client.get("/systems/erp/purchase_orders", params={"supplier_id": "SUP-007"}).json()
    assert sorted(i["po_id"] for i in apex["items"]) == ["PO-10198", "PO-10233", "PO-10240"]


def test_late_rule() -> None:
    from datetime import date

    on = date(2026, 10, 1)
    assert is_late("OPEN", date(2026, 9, 15), date(2026, 10, 20), on)
    assert not is_late("OPEN", date(2026, 11, 1), date(2026, 11, 1), on)
    assert is_late("OPEN", date(2026, 9, 20), date(2026, 9, 20), on)
    assert not is_late("RECEIVED", date(2026, 7, 1), date(2026, 7, 1), on)
