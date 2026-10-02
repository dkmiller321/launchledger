"""Deterministic seed (PRD S5, E2E_TESTS.md §1.4): pinned demo records + RNG(42) fill."""

import hashlib
import json
import random
from datetime import date, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from launchledger.db import models as m

TOTALS = {
    "parts": 120,
    "bom_lines": 200,
    "serials": 300,
    "work_orders": 400,
    "inspections": 250,
    "nonconformances": 80,
    "suppliers": 25,
    "purchase_orders": 600,
    "requirements": 60,
}

D = date.fromisoformat

SUPPLIERS = [
    ("SUP-007", "Apex Castings"),
    ("SUP-012", "Orbital Fasteners"),
    ("SUP-019", "Cryo Valve Works"),
]

PARTS = [
    (
        "P-1077",
        "Turbopump inducer housing",
        "C",
        14.2,
        18450.00,
        True,
        "Inducer blade angle 11.5 deg; CMM tolerance 0.02 mm",
    ),
    (
        "P-2001",
        "LOX turbopump assembly",
        "B",
        96.5,
        412000.00,
        True,
        "Shaft seal stack-up per HX-77",
    ),
    (
        "P-2110",
        "Fuel turbopump assembly",
        "B",
        88.0,
        398000.00,
        True,
        "Impeller balance grade G1.0",
    ),
    ("P-1500", "Stage 2 tank dome", "A", 212.5, 96000.00, False, None),
    ("P-3300", "Engine controller harness", "D", 6.8, 22300.00, False, None),
]

BOM = [
    ("BL-0001", "P-2001", "P-1077", 1),
    ("BL-0002", "P-2110", "P-1077", 1),
    ("BL-0003", "P-2001", "P-3300", 1),
]

SERIALS = [
    ("SN-0042", "P-2001", "B", "IN_BUILD", "Bay 3 - Engine Integration"),
    ("SN-0057", "P-2110", "B", "IN_BUILD", "Bay 3 - Engine Integration"),
    ("SN-0101", "P-1500", "A", "COMPLETE", "Stores - Building 2"),
    ("SN-0120", "P-2001", "B", "PLANNED", "Bay 1 - Kitting"),
]

WORK_ORDERS = [
    (
        "WO-50101",
        "SN-0042",
        "CLOSED",
        None,
        None,
        "Machine housing interfaces",
        D("2026-08-03"),
        D("2026-08-20"),
    ),
    (
        "WO-50102",
        "SN-0042",
        "BLOCKED",
        "Awaiting inducer housing castings",
        "PO-10233",
        "Install inducer housing",
        D("2026-08-21"),
        None,
    ),
    (
        "WO-50103",
        "SN-0042",
        "OPEN",
        None,
        None,
        "Final assembly and leak check",
        D("2026-09-01"),
        None,
    ),
    (
        "WO-50217",
        "SN-0057",
        "OPEN",
        None,
        "PO-10233",
        "Install inducer housing",
        D("2026-09-05"),
        None,
    ),
    (
        "WO-50300",
        "SN-0101",
        "CLOSED",
        None,
        None,
        "Dome weld and X-ray",
        D("2026-07-01"),
        D("2026-07-25"),
    ),
    (
        "WO-50410",
        "SN-0120",
        "OPEN",
        None,
        "PO-10410",
        "Install controller harness",
        D("2026-09-22"),
        None,
    ),
]

INSPECTIONS = [
    ("INS-7001", "SN-0042", "PASS", D("2026-09-10")),
    ("INS-7002", "SN-0101", "PASS", D("2026-08-21")),
]

NCRS = [
    ("NCR-0311", "SN-0042", "MAJOR", "OPEN", "REQ-118", "Porosity in casting flange"),
    ("NCR-0298", "SN-0042", "MINOR", "CLOSED", "REQ-104", "Scratch on mounting face"),
    ("NCR-0320", "SN-0057", "MINOR", "OPEN", "REQ-118", "Flange surface pitting"),
]

PURCHASE_ORDERS = [
    ("PO-10233", "SUP-007", "P-1077", 4, D("2026-09-15"), D("2026-10-20"), "OPEN", 18450.00, None),
    ("PO-10240", "SUP-007", "P-1077", 2, D("2026-11-01"), D("2026-11-01"), "OPEN", 18450.00, None),
    (
        "PO-10198",
        "SUP-007",
        "P-1077",
        2,
        D("2026-07-01"),
        D("2026-07-01"),
        "RECEIVED",
        18100.00,
        D("2026-06-28"),
    ),
    ("PO-10300", "SUP-012", "P-3300", 10, D("2026-10-15"), D("2026-10-15"), "OPEN", 22300.00, None),
    ("PO-10410", "SUP-019", "P-3300", 5, D("2026-09-20"), D("2026-09-20"), "OPEN", 22300.00, None),
]

REQUIREMENTS = [
    ("REQ-118", "Casting porosity limited to ASTM E505 level 2", "Inspection"),
    ("REQ-104", "Mounting face finish 63 Ra max", "Inspection"),
]
REQ_LINKS = [("REQ-118", "P-1077"), ("REQ-104", "P-2001")]

_NOUNS = [
    "bracket",
    "valve",
    "manifold",
    "flange",
    "harness",
    "sensor",
    "nozzle",
    "duct",
    "actuator",
    "seal kit",
    "bolt set",
    "injector",
    "igniter",
    "panel",
    "strut",
    "liner",
]
_ADJS = [
    "LOX",
    "fuel",
    "helium",
    "aft",
    "forward",
    "upper",
    "lower",
    "thrust",
    "gimbal",
    "pressurant",
    "avionics",
    "cryogenic",
]
_LOCATIONS = [
    "Bay 1 - Kitting",
    "Bay 2 - Machining",
    "Bay 3 - Engine Integration",
    "Bay 4 - Stage Integration",
    "Stores - Building 2",
    "Test Stand A",
]
_SUPPLIER_WORDS = [
    "Northline",
    "Cascade",
    "Summit",
    "Ironwood",
    "Bluewater",
    "Redstone",
    "Pioneer",
    "Granite",
    "Helix",
    "Vector",
    "Keystone",
]
_SUPPLIER_KINDS = ["Machining", "Composites", "Electronics", "Forge", "Plating", "Valves"]
_BLOCK_REASONS = [
    "Awaiting parts",
    "Awaiting engineering disposition",
    "Tooling down",
    "Awaiting inspection",
]
_NCR_TEXTS = [
    "Dimension out of tolerance",
    "Surface scratch",
    "Weld undercut",
    "Missing torque stripe",
    "Incorrect revision installed",
    "Contamination found",
]


def _day(rng: random.Random, start: str, end: str) -> date:
    a, b = D(start), D(end)
    return a + timedelta(days=rng.randint(0, (b - a).days))


def build_rows() -> dict[str, list[dict[str, Any]]]:
    """All system rows, pinned first then random. Pure and deterministic."""
    rng = random.Random(42)
    rows: dict[str, list[dict[str, Any]]] = {k: [] for k in TOTALS}
    rows["req_links"] = []

    rows["suppliers"] = [{"supplier_id": i, "name": n} for i, n in SUPPLIERS]
    rnd_suppliers = []
    for k in range(TOTALS["suppliers"] - len(SUPPLIERS)):
        sid = f"SUP-{100 + k}"
        name = f"{rng.choice(_SUPPLIER_WORDS)} {rng.choice(_SUPPLIER_KINDS)} {k + 1}"
        rows["suppliers"].append({"supplier_id": sid, "name": name})
        rnd_suppliers.append(sid)

    for pn, name, rev, mass, cost, ctrl, notes in PARTS:
        rows["parts"].append(
            {
                "part_number": pn,
                "name": name,
                "revision": rev,
                "mass_kg": mass,
                "unit_cost_usd": cost,
                "export_controlled": ctrl,
                "controlled_notes": notes,
            }
        )
    rnd_parts: list[tuple[str, float]] = []
    for k in range(TOTALS["parts"] - len(PARTS)):
        pn = f"P-{4000 + k}"
        ctrl = rng.random() < 0.2
        cost = round(10 ** rng.uniform(1, 5.3), 2)
        rows["parts"].append(
            {
                "part_number": pn,
                "name": f"{rng.choice(_ADJS).capitalize()} {rng.choice(_NOUNS)}",
                "revision": rng.choice("ABCDE"),
                "mass_kg": round(10 ** rng.uniform(-1, 2.5), 2),
                "unit_cost_usd": cost,
                "export_controlled": ctrl,
                "controlled_notes": f"Process spec PS-{rng.randint(100, 999)}" if ctrl else None,
            }
        )
        rnd_parts.append((pn, cost))

    rows["bom_lines"] = [
        {"bom_line_id": b, "parent_pn": p, "child_pn": c, "qty": q} for b, p, c, q in BOM
    ]
    seen: set[tuple[str, str]] = set()
    k = 0
    while len(rows["bom_lines"]) < TOTALS["bom_lines"]:
        parent, child = rng.sample(rnd_parts, 2)
        if (parent[0], child[0]) in seen:
            continue
        seen.add((parent[0], child[0]))
        rows["bom_lines"].append(
            {
                "bom_line_id": f"BL-{1000 + k}",
                "parent_pn": parent[0],
                "child_pn": child[0],
                "qty": rng.randint(1, 8),
            }
        )
        k += 1

    rows["serials"] = [
        {"serial_number": s, "part_number": p, "revision": r, "status": st, "location": loc}
        for s, p, r, st, loc in SERIALS
    ]
    rnd_serials = []
    for k in range(TOTALS["serials"] - len(SERIALS)):
        sn = f"SN-{1000 + k}"
        part = rng.choice(rnd_parts)[0]
        rows["serials"].append(
            {
                "serial_number": sn,
                "part_number": part,
                "revision": rng.choice("ABCDE"),
                "status": rng.choice(["PLANNED", "IN_BUILD", "IN_BUILD", "COMPLETE"]),
                "location": rng.choice(_LOCATIONS),
            }
        )
        rnd_serials.append(sn)

    rows["purchase_orders"] = [
        {
            "po_id": po,
            "supplier_id": sup,
            "part_number": pn,
            "qty": q,
            "due_date": due,
            "promised_date": prom,
            "status": st,
            "unit_cost_usd": cost,
            "received_on": rec,
        }
        for po, sup, pn, q, due, prom, st, cost, rec in PURCHASE_ORDERS
    ]
    rnd_pos = []
    for k in range(TOTALS["purchase_orders"] - len(PURCHASE_ORDERS)):
        po = f"PO-{20000 + k}"
        part, base_cost = rng.choice(rnd_parts)
        due = _day(rng, "2026-04-01", "2026-12-31")
        prom = due + timedelta(days=rng.choice([0, 0, 0, 0, 7, 14, 30]))
        if rng.random() < 0.05:
            status = "CANCELLED"
        elif due < D("2026-08-15") or rng.random() < 0.15:
            status = "RECEIVED"
        else:
            status = "OPEN"
        received = prom + timedelta(days=rng.randint(-5, 10)) if status == "RECEIVED" else None
        rows["purchase_orders"].append(
            {
                "po_id": po,
                "supplier_id": rng.choice(rnd_suppliers),
                "part_number": part,
                "qty": rng.randint(1, 50),
                "due_date": due,
                "promised_date": prom,
                "status": status,
                "unit_cost_usd": round(base_cost * rng.uniform(0.95, 1.05), 2),
                "received_on": received,
            }
        )
        rnd_pos.append(po)

    rows["work_orders"] = [
        {
            "wo_id": w,
            "serial_number": s,
            "status": st,
            "blocked_reason": br,
            "depends_on_po": po,
            "description": desc,
            "opened_on": op,
            "closed_on": cl,
        }
        for w, s, st, br, po, desc, op, cl in WORK_ORDERS
    ]
    for k in range(TOTALS["work_orders"] - len(WORK_ORDERS)):
        status = rng.choice(["OPEN", "IN_PROGRESS", "BLOCKED", "CLOSED", "CLOSED"])
        opened = _day(rng, "2026-03-01", "2026-09-28")
        closed = opened + timedelta(days=rng.randint(2, 40)) if status == "CLOSED" else None
        depends = rng.choice(rnd_pos) if status != "CLOSED" and rng.random() < 0.3 else None
        rows["work_orders"].append(
            {
                "wo_id": f"WO-{60000 + k}",
                "serial_number": rng.choice(rnd_serials),
                "status": status,
                "blocked_reason": rng.choice(_BLOCK_REASONS) if status == "BLOCKED" else None,
                "depends_on_po": depends,
                "description": f"{rng.choice(['Install', 'Machine', 'Inspect', 'Torque', 'Test'])} "
                f"{rng.choice(_NOUNS)}",
                "opened_on": opened,
                "closed_on": closed,
            }
        )

    rows["inspections"] = [
        {"inspection_id": i, "serial_number": s, "result": r, "inspected_at": d}
        for i, s, r, d in INSPECTIONS
    ]
    for k in range(TOTALS["inspections"] - len(INSPECTIONS)):
        rows["inspections"].append(
            {
                "inspection_id": f"INS-{8000 + k}",
                "serial_number": rng.choice(rnd_serials),
                "result": "PASS" if rng.random() < 0.85 else "FAIL",
                "inspected_at": _day(rng, "2026-03-01", "2026-09-30"),
            }
        )

    rows["requirements"] = [
        {"req_id": r, "text": t, "verification_method": v} for r, t, v in REQUIREMENTS
    ]
    rnd_reqs = []
    for k in range(TOTALS["requirements"] - len(REQUIREMENTS)):
        rid = f"REQ-{200 + k}"
        rows["requirements"].append(
            {
                "req_id": rid,
                "text": f"{rng.choice(_ADJS).capitalize()} {rng.choice(_NOUNS)} shall meet "
                f"spec HS-{rng.randint(1000, 9999)}",
                "verification_method": rng.choice(
                    ["Inspection", "Test", "Analysis", "Demonstration"]
                ),
            }
        )
        rnd_reqs.append(rid)
        rows["req_links"].append({"req_id": rid, "part_number": rng.choice(rnd_parts)[0]})
    rows["req_links"][:0] = [{"req_id": r, "part_number": p} for r, p in REQ_LINKS]

    rows["nonconformances"] = [
        {
            "ncr_id": n,
            "serial_number": s,
            "severity": sev,
            "status": st,
            "requirement_id": r,
            "description": desc,
        }
        for n, s, sev, st, r, desc in NCRS
    ]
    for k in range(TOTALS["nonconformances"] - len(NCRS)):
        rows["nonconformances"].append(
            {
                "ncr_id": f"NCR-{1000 + k}",
                "serial_number": rng.choice(rnd_serials),
                "severity": rng.choice(["MINOR", "MINOR", "MAJOR", "CRITICAL"]),
                "status": rng.choice(["OPEN", "CLOSED", "CLOSED"]),
                "requirement_id": rng.choice(rnd_reqs),
                "description": rng.choice(_NCR_TEXTS),
            }
        )
    return rows


TABLE_MODELS: dict[str, Any] = {
    "suppliers": m.Supplier,
    "parts": m.Part,
    "bom_lines": m.BomLine,
    "serials": m.Serial,
    "purchase_orders": m.PurchaseOrder,
    "work_orders": m.WorkOrder,
    "inspections": m.Inspection,
    "nonconformances": m.Nonconformance,
    "requirements": m.Requirement,
    "req_links": m.RequirementPartLink,
}


def seed(session: Session) -> None:
    """Replace every system table's contents with the deterministic seed."""
    for model in (*TABLE_MODELS.values(), m.SupplierOnTime, m.WoCycleTime):
        session.execute(delete(model))
    for table, rows in build_rows().items():
        session.execute(TABLE_MODELS[table].__table__.insert(), rows)
    session.flush()
    from launchledger.systems.dw import rebuild_dw

    rebuild_dw(session)


def is_seeded(session: Session) -> bool:
    return bool(session.scalar(select(func.count()).select_from(m.Part)))


def seed_hash(session: Session) -> str:
    digest = hashlib.sha256()
    for table, model in TABLE_MODELS.items():
        table_obj = model.__table__
        rows = (
            session.execute(select(table_obj).order_by(*table_obj.primary_key.columns))
            .mappings()
            .all()
        )
        digest.update(table.encode())
        digest.update(json.dumps([dict(r) for r in rows], default=str, sort_keys=True).encode())
    return digest.hexdigest()
