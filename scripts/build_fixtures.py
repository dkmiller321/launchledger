"""Generate fixtures/llm-mock.json and evals/cases/*.yaml from one source of truth.

Every golden case has a mock script keyed by its question, and its expected facts are the
facts that script cites. Test-only scripts (M7-M14) are mock scripts without a golden case.
Run: uv run python scripts/build_fixtures.py
"""

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent


def F(system: str, rtype: str, rid: str, field: str, value: Any) -> dict[str, Any]:
    return {
        "system": system,
        "record_type": rtype,
        "record_id": rid,
        "field": field,
        "value": value,
    }


def T(tool: str, **args: Any) -> dict[str, Any]:
    return {"name": tool, "arguments": args}


class Spec:
    def __init__(
        self,
        case_id: str | None,
        question: str,
        workflow: str,
        tools: list[list[dict[str, Any]]],
        answer: str | None = None,
        claims: list[tuple[str, list[dict[str, Any]]]] | None = None,
        caveats: list[str] | None = None,
        decision: str = "answered",
        trigger: str | None = None,
        raw: list[str] | None = None,
    ) -> None:
        self.case_id = case_id
        self.question = question
        self.workflow = workflow
        self.trigger = (trigger or question).lower()
        steps: list[dict[str, Any]] = [{"tool_calls": calls} for calls in tools]
        steps += [{"raw": r} for r in raw or []]
        self.claims = claims or []
        if answer is not None:
            steps.append(
                {
                    "final": {
                        "answer": answer,
                        "claims": [{"text": text, "facts": facts} for text, facts in self.claims],
                        "caveats": caveats or [],
                    }
                }
            )
        self.steps = steps
        self.decision = decision

    def expected_facts(self) -> list[dict[str, Any]]:
        return [f for _, facts in self.claims for f in facts]


def S(sn: str, field: str, value: Any) -> dict[str, Any]:
    return F("MES", "serial", sn, field, value)


def WO(wo: str, field: str, value: Any) -> dict[str, Any]:
    return F("MES", "work_order", wo, field, value)


def NCR(ncr: str, field: str, value: Any) -> dict[str, Any]:
    return F("MES", "ncr", ncr, field, value)


def PO(po: str, field: str, value: Any) -> dict[str, Any]:
    return F("ERP", "purchase_order", po, field, value)


def SUP(sid: str, name: str) -> dict[str, Any]:
    return F("ERP", "supplier", sid, "name", name)


def BL(bl: str, field: str, value: Any) -> dict[str, Any]:
    return F("PLM", "bom_line", bl, field, value)


M1 = "Where is SN-0042 and what's blocking it?"
M2 = "Which open work orders are at risk from late POs from Apex Castings?"
M3 = "Which assemblies use part P-1077?"
M4 = "What open nonconformances are there against SN-0042?"
M5 = "What's the status of PO-10233 and is it late?"
M6 = "Is SN-0042 ready for stage integration?"

GOLDEN: list[Spec] = [
    # --- W1 serial_status -------------------------------------------------------------------
    Spec(
        "W1-01",
        M1,
        "serial_status",
        [
            [T("get_serial", serial_number="SN-0042")],
            [T("list_work_orders", serial_number="SN-0042")],
        ],
        "SN-0042 is IN_BUILD at Bay 3 - Engine Integration. It is blocked by WO-50102 "
        "(Awaiting inducer housing castings), which depends on PO-10233. WO-50103 is still OPEN.",
        [
            (
                "SN-0042 is in build at Bay 3.",
                [
                    S("SN-0042", "status", "IN_BUILD"),
                    S("SN-0042", "location", "Bay 3 - Engine Integration"),
                ],
            ),
            (
                "WO-50102 is blocked waiting for castings on PO-10233.",
                [
                    WO("WO-50102", "status", "BLOCKED"),
                    WO("WO-50102", "blocked_reason", "Awaiting inducer housing castings"),
                    WO("WO-50102", "depends_on_po", "PO-10233"),
                ],
            ),
            ("WO-50103 is open.", [WO("WO-50103", "status", "OPEN")]),
        ],
        trigger="where is sn-0042",
    ),
    Spec(
        "W1-02",
        "Where is SN-0057 right now?",
        "serial_status",
        [
            [T("get_serial", serial_number="SN-0057")],
            [T("list_work_orders", serial_number="SN-0057")],
        ],
        "SN-0057 is IN_BUILD at Bay 3 - Engine Integration. WO-50217 is OPEN and depends on "
        "PO-10233.",
        [
            (
                "SN-0057 is in build at Bay 3.",
                [
                    S("SN-0057", "status", "IN_BUILD"),
                    S("SN-0057", "location", "Bay 3 - Engine Integration"),
                ],
            ),
            (
                "WO-50217 is open and waits on PO-10233.",
                [WO("WO-50217", "status", "OPEN"), WO("WO-50217", "depends_on_po", "PO-10233")],
            ),
        ],
    ),
    Spec(
        "W1-03",
        "Where is SN-0101?",
        "serial_status",
        [
            [T("get_serial", serial_number="SN-0101")],
            [T("list_work_orders", serial_number="SN-0101")],
        ],
        "SN-0101 is COMPLETE in Stores - Building 2. Its only work order, WO-50300, is CLOSED.",
        [
            (
                "SN-0101 is complete and in stores.",
                [
                    S("SN-0101", "status", "COMPLETE"),
                    S("SN-0101", "location", "Stores - Building 2"),
                ],
            ),
            ("WO-50300 is closed.", [WO("WO-50300", "status", "CLOSED")]),
        ],
    ),
    Spec(
        "W1-04",
        "Where is SN-0404?",
        "serial_status",
        [[T("get_serial", serial_number="SN-0404")]],
        "I couldn't find SN-0404 in MES.",
        [],
        ["SN-0404 was not found in MES."],
    ),
    Spec(
        "W1-05",
        "What's the current status of SN-0120?",
        "serial_status",
        [
            [T("get_serial", serial_number="SN-0120")],
            [T("list_work_orders", serial_number="SN-0120")],
        ],
        "SN-0120 is PLANNED in Bay 1 - Kitting. WO-50410 is OPEN and depends on PO-10410.",
        [
            (
                "SN-0120 is planned and in kitting.",
                [S("SN-0120", "status", "PLANNED"), S("SN-0120", "location", "Bay 1 - Kitting")],
            ),
            (
                "WO-50410 is open and waits on PO-10410.",
                [WO("WO-50410", "status", "OPEN"), WO("WO-50410", "depends_on_po", "PO-10410")],
            ),
        ],
    ),
    # --- W2 supplier_impact -----------------------------------------------------------------
    Spec(
        "W2-01",
        M2,
        "supplier_impact",
        [
            [T("find_supplier", name="Apex Castings")],
            [T("list_pos", supplier_id="SUP-007", status="OPEN")],
            [T("list_work_orders", depends_on_po="PO-10233")],
        ],
        "Apex Castings has one late open PO: PO-10233, due 2026-09-15 but now promised "
        "2026-10-20. Two work orders depend on it: WO-50102 (BLOCKED) and WO-50217 (OPEN). "
        "PO-10240 is on time.",
        [
            (
                "PO-10233 from Apex Castings is late.",
                [
                    SUP("SUP-007", "Apex Castings"),
                    PO("PO-10233", "status", "OPEN"),
                    PO("PO-10233", "due_date", "2026-09-15"),
                    PO("PO-10233", "promised_date", "2026-10-20"),
                ],
            ),
            (
                "WO-50102 and WO-50217 depend on PO-10233.",
                [
                    WO("WO-50102", "depends_on_po", "PO-10233"),
                    WO("WO-50217", "depends_on_po", "PO-10233"),
                ],
            ),
            (
                "PO-10240 is on time.",
                [
                    PO("PO-10240", "due_date", "2026-11-01"),
                    PO("PO-10240", "promised_date", "2026-11-01"),
                ],
            ),
        ],
        trigger="late pos from apex castings",
    ),
    Spec(
        "W2-02",
        "Are any work orders at risk from late POs from Orbital Fasteners?",
        "supplier_impact",
        [
            [T("find_supplier", name="Orbital Fasteners")],
            [T("list_pos", supplier_id="SUP-012", status="OPEN")],
        ],
        "Orbital Fasteners has no late open POs: PO-10300 is due 2026-10-15 and promised for "
        "the same day, so no work orders are at risk from them.",
        [
            (
                "Orbital Fasteners' only open PO is on time.",
                [
                    SUP("SUP-012", "Orbital Fasteners"),
                    PO("PO-10300", "due_date", "2026-10-15"),
                    PO("PO-10300", "promised_date", "2026-10-15"),
                ],
            )
        ],
    ),
    Spec(
        "W2-03",
        "Which work orders are at risk from late POs from Cryo Valve Works?",
        "supplier_impact",
        [
            [T("find_supplier", name="Cryo Valve Works")],
            [T("list_pos", supplier_id="SUP-019", status="OPEN")],
            [T("list_work_orders", depends_on_po="PO-10410")],
        ],
        "Cryo Valve Works has one late open PO: PO-10410 was due 2026-09-20 and is still OPEN. "
        "WO-50410 depends on it.",
        [
            (
                "PO-10410 from Cryo Valve Works is past due.",
                [
                    SUP("SUP-019", "Cryo Valve Works"),
                    PO("PO-10410", "status", "OPEN"),
                    PO("PO-10410", "due_date", "2026-09-20"),
                ],
            ),
            ("WO-50410 depends on PO-10410.", [WO("WO-50410", "depends_on_po", "PO-10410")]),
        ],
    ),
    Spec(
        "W2-04",
        "Which work orders are at risk from late POs from Acme Rockets?",
        "supplier_impact",
        [[T("find_supplier", name="Acme Rockets")]],
        "No supplier named Acme Rockets was found in ERP, so I can't assess its POs.",
        [],
        ["No supplier named Acme Rockets was found in ERP."],
    ),
    Spec(
        "W2-05",
        "Which open work orders depend on PO-10233?",
        "supplier_impact",
        [[T("list_work_orders", depends_on_po="PO-10233")]],
        "Two work orders depend on PO-10233: WO-50102 (BLOCKED) and WO-50217 (OPEN).",
        [
            (
                "WO-50102 and WO-50217 depend on PO-10233.",
                [
                    WO("WO-50102", "depends_on_po", "PO-10233"),
                    WO("WO-50102", "status", "BLOCKED"),
                    WO("WO-50217", "depends_on_po", "PO-10233"),
                    WO("WO-50217", "status", "OPEN"),
                ],
            )
        ],
    ),
    # --- W3 where_used ----------------------------------------------------------------------
    Spec(
        "W3-01",
        M3,
        "where_used",
        [[T("where_used", part_number="P-1077")]],
        "P-1077 is used in two assemblies: P-2001 and P-2110, quantity 1 in each.",
        [
            (
                "P-1077 is used once in P-2001 and once in P-2110.",
                [
                    BL("BL-0001", "parent_pn", "P-2001"),
                    BL("BL-0001", "qty", 1),
                    BL("BL-0002", "parent_pn", "P-2110"),
                    BL("BL-0002", "qty", 1),
                ],
            )
        ],
        trigger="which assemblies use part p-1077",
    ),
    Spec(
        "W3-02",
        "Which assemblies use part P-3300?",
        "where_used",
        [[T("where_used", part_number="P-3300")]],
        "P-3300 is used in one assembly: P-2001, quantity 1.",
        [
            (
                "P-3300 is used once in P-2001.",
                [BL("BL-0003", "parent_pn", "P-2001"), BL("BL-0003", "qty", 1)],
            )
        ],
    ),
    Spec(
        "W3-03",
        "What's in the bill of materials for P-2001?",
        "where_used",
        [[T("get_bom", part_number="P-2001")]],
        "P-2001 contains P-1077 (quantity 1) and P-3300 (quantity 1).",
        [
            (
                "P-2001 contains P-1077 and P-3300.",
                [
                    BL("BL-0001", "child_pn", "P-1077"),
                    BL("BL-0001", "qty", 1),
                    BL("BL-0003", "child_pn", "P-3300"),
                    BL("BL-0003", "qty", 1),
                ],
            )
        ],
    ),
    Spec(
        "W3-04",
        "Which assemblies use part P-1500?",
        "where_used",
        [[T("where_used", part_number="P-1500")]],
        "No assemblies in PLM use P-1500.",
        [],
        ["PLM lists no BOM lines that use P-1500."],
    ),
    Spec(
        "W3-05",
        "Which assemblies use part P-9999?",
        "where_used",
        [[T("where_used", part_number="P-9999")]],
        "I couldn't find part P-9999 in PLM.",
        [],
        ["P-9999 was not found in PLM."],
    ),
    # --- W4 ncr_summary ---------------------------------------------------------------------
    Spec(
        "W4-01",
        M4,
        "ncr_summary",
        [[T("list_ncrs", serial_number="SN-0042", status="OPEN")]],
        "SN-0042 has one open nonconformance: NCR-0311 (MAJOR), Porosity in casting flange, "
        "against REQ-118.",
        [
            (
                "NCR-0311 is an open major NCR against REQ-118.",
                [
                    NCR("NCR-0311", "status", "OPEN"),
                    NCR("NCR-0311", "severity", "MAJOR"),
                    NCR("NCR-0311", "description", "Porosity in casting flange"),
                    NCR("NCR-0311", "requirement_id", "REQ-118"),
                ],
            )
        ],
        trigger="open nonconformances",
    ),
    Spec(
        "W4-02",
        "List all nonconformances against SN-0042",
        "ncr_summary",
        [[T("list_ncrs", serial_number="SN-0042")]],
        "SN-0042 has two nonconformances: NCR-0311 (MAJOR, OPEN) and NCR-0298 (MINOR, CLOSED).",
        [
            (
                "NCR-0311 is major and open.",
                [NCR("NCR-0311", "status", "OPEN"), NCR("NCR-0311", "severity", "MAJOR")],
            ),
            (
                "NCR-0298 is minor and closed.",
                [NCR("NCR-0298", "status", "CLOSED"), NCR("NCR-0298", "severity", "MINOR")],
            ),
        ],
    ),
    Spec(
        "W4-03",
        "Does SN-0101 have any NCRs?",
        "ncr_summary",
        [[T("list_ncrs", serial_number="SN-0101")]],
        "SN-0101 has no nonconformances in MES.",
        [],
        ["MES returned no NCRs for SN-0101."],
    ),
    Spec(
        "W4-04",
        "Which NCRs are open on part P-2110?",
        "ncr_summary",
        [[T("list_ncrs", part_number="P-2110", status="OPEN")]],
        "One NCR is open on P-2110: NCR-0320 (MINOR) on SN-0057, Flange surface pitting.",
        [
            (
                "NCR-0320 is open on SN-0057.",
                [
                    NCR("NCR-0320", "status", "OPEN"),
                    NCR("NCR-0320", "severity", "MINOR"),
                    NCR("NCR-0320", "serial_number", "SN-0057"),
                    NCR("NCR-0320", "description", "Flange surface pitting"),
                ],
            )
        ],
    ),
    Spec(
        "W4-05",
        "Show NCR details for SN-0057",
        "ncr_summary",
        [[T("list_ncrs", serial_number="SN-0057")]],
        "SN-0057 has one nonconformance: NCR-0320, MINOR and OPEN, Flange surface pitting, "
        "against REQ-118.",
        [
            (
                "NCR-0320 is a minor open NCR against REQ-118.",
                [
                    NCR("NCR-0320", "description", "Flange surface pitting"),
                    NCR("NCR-0320", "severity", "MINOR"),
                    NCR("NCR-0320", "status", "OPEN"),
                    NCR("NCR-0320", "requirement_id", "REQ-118"),
                ],
            )
        ],
    ),
    # --- W5 po_status -----------------------------------------------------------------------
    Spec(
        "W5-01",
        M5,
        "po_status",
        [[T("get_po", po_id="PO-10233")], [T("get_supplier", supplier_id="SUP-007")]],
        "PO-10233 from Apex Castings is OPEN and late: it was due 2026-09-15 and is now "
        "promised for 2026-10-20.",
        [
            (
                "PO-10233 is open and promised after its due date.",
                [
                    PO("PO-10233", "status", "OPEN"),
                    PO("PO-10233", "due_date", "2026-09-15"),
                    PO("PO-10233", "promised_date", "2026-10-20"),
                    PO("PO-10233", "supplier_id", "SUP-007"),
                    SUP("SUP-007", "Apex Castings"),
                ],
            )
        ],
        trigger="status of po-10233",
    ),
    Spec(
        "W5-02",
        "What's the status of PO-10240?",
        "po_status",
        [[T("get_po", po_id="PO-10240")], [T("get_supplier", supplier_id="SUP-007")]],
        "PO-10240 from Apex Castings is OPEN and on time: due and promised for 2026-11-01.",
        [
            (
                "PO-10240 is open and on time.",
                [
                    PO("PO-10240", "status", "OPEN"),
                    PO("PO-10240", "due_date", "2026-11-01"),
                    PO("PO-10240", "promised_date", "2026-11-01"),
                    SUP("SUP-007", "Apex Castings"),
                ],
            )
        ],
    ),
    Spec(
        "W5-03",
        "Has PO-10198 been received?",
        "po_status",
        [[T("get_po", po_id="PO-10198")]],
        "Yes. PO-10198 is RECEIVED; it arrived on 2026-06-28, ahead of its 2026-07-01 due date.",
        [
            (
                "PO-10198 was received early.",
                [
                    PO("PO-10198", "status", "RECEIVED"),
                    PO("PO-10198", "received_on", "2026-06-28"),
                    PO("PO-10198", "due_date", "2026-07-01"),
                ],
            )
        ],
    ),
    Spec(
        "W5-04",
        "Is PO-10410 late?",
        "po_status",
        [[T("get_po", po_id="PO-10410")], [T("get_supplier", supplier_id="SUP-019")]],
        "Yes. PO-10410 from Cryo Valve Works is OPEN and past its 2026-09-20 due date.",
        [
            (
                "PO-10410 is open and past due.",
                [
                    PO("PO-10410", "status", "OPEN"),
                    PO("PO-10410", "due_date", "2026-09-20"),
                    SUP("SUP-019", "Cryo Valve Works"),
                ],
            )
        ],
    ),
    Spec(
        "W5-05",
        "What's the status of PO-99999?",
        "po_status",
        [[T("get_po", po_id="PO-99999")]],
        "I couldn't find PO-99999 in ERP.",
        [],
        ["PO-99999 was not found in ERP."],
    ),
    # --- W6 build_readiness -----------------------------------------------------------------
    Spec(
        "W6-01",
        M6,
        "build_readiness",
        [
            [T("list_work_orders", serial_number="SN-0042")],
            [T("list_inspections", serial_number="SN-0042")],
            [T("list_ncrs", serial_number="SN-0042", status="OPEN")],
        ],
        "No. SN-0042 is not ready for stage integration: WO-50102 is BLOCKED, WO-50103 is OPEN "
        "and NCR-0311 is still OPEN. Inspection INS-7001 passed.",
        [
            (
                "Two work orders are not closed.",
                [WO("WO-50102", "status", "BLOCKED"), WO("WO-50103", "status", "OPEN")],
            ),
            ("NCR-0311 is still open.", [NCR("NCR-0311", "status", "OPEN")]),
            ("Inspection INS-7001 passed.", [F("MES", "inspection", "INS-7001", "result", "PASS")]),
        ],
        trigger="ready for stage integration",
    ),
    Spec(
        "W6-02",
        "Is SN-0101 ready to ship?",
        "build_readiness",
        [
            [T("list_work_orders", serial_number="SN-0101")],
            [T("list_inspections", serial_number="SN-0101")],
            [T("list_ncrs", serial_number="SN-0101", status="OPEN")],
        ],
        "Yes. SN-0101's only work order WO-50300 is CLOSED and inspection INS-7002 passed; MES "
        "shows no open NCRs.",
        [
            ("WO-50300 is closed.", [WO("WO-50300", "status", "CLOSED")]),
            ("INS-7002 passed.", [F("MES", "inspection", "INS-7002", "result", "PASS")]),
        ],
        ["MES returned no open NCRs for SN-0101."],
    ),
    Spec(
        "W6-03",
        "Is SN-0057 ready for integration?",
        "build_readiness",
        [
            [T("list_work_orders", serial_number="SN-0057")],
            [T("list_inspections", serial_number="SN-0057")],
            [T("list_ncrs", serial_number="SN-0057", status="OPEN")],
        ],
        "No. SN-0057 is not ready: WO-50217 is OPEN, NCR-0320 is OPEN, and no inspection is "
        "recorded.",
        [
            ("WO-50217 is open.", [WO("WO-50217", "status", "OPEN")]),
            ("NCR-0320 is open.", [NCR("NCR-0320", "status", "OPEN")]),
        ],
        ["MES has no inspections for SN-0057."],
    ),
    Spec(
        "W6-04",
        "Is SN-0120 ready for integration?",
        "build_readiness",
        [
            [T("list_work_orders", serial_number="SN-0120")],
            [T("list_inspections", serial_number="SN-0120")],
            [T("list_ncrs", serial_number="SN-0120", status="OPEN")],
        ],
        "No. SN-0120 is not ready: WO-50410 is still OPEN and no inspection is recorded.",
        [("WO-50410 is open.", [WO("WO-50410", "status", "OPEN")])],
        ["MES has no inspections or open NCRs for SN-0120."],
    ),
    Spec(
        "W6-05",
        "Is SN-0404 ready for integration?",
        "build_readiness",
        [[T("get_serial", serial_number="SN-0404")]],
        "I couldn't find SN-0404 in MES.",
        [],
        ["SN-0404 was not found in MES."],
    ),
]

# Test-only scripts (E2E_TESTS.md §1.6, M7-M14). M11 is the same script as W1-04.
TEST_ONLY: list[Spec] = [
    Spec(
        None,
        "ghost serial test",
        "serial_status",
        [[T("get_serial", serial_number="SN-0042")]],
        "SN-0042 is IN_BUILD. Its sister unit SN-9999 is complete.",
        [("SN-0042 is in build.", [S("SN-0042", "status", "IN_BUILD")])],
    ),
    Spec(
        None,
        "wrong status test",
        "serial_status",
        [[T("get_serial", serial_number="SN-0042")]],
        "SN-0042 has shipped.",
        [("SN-0042 has shipped.", [S("SN-0042", "status", "SHIPPED")])],
    ),
    Spec(
        None,
        "uncited claim test",
        "serial_status",
        [[T("get_serial", serial_number="SN-0042")]],
        "SN-0042 is in build.",
        [("SN-0042 is in build.", [])],
    ),
    Spec(
        None,
        "inducer details test",
        "where_used",
        [[T("get_part", part_number="P-1077")]],
        "P-1077 has an inducer blade angle of 11.5 deg.",
        [
            (
                "P-1077's inducer blade angle is 11.5 deg.",
                [
                    F(
                        "PLM",
                        "part",
                        "P-1077",
                        "controlled_notes",
                        "Inducer blade angle 11.5 deg; CMM tolerance 0.02 mm",
                    )
                ],
            )
        ],
    ),
    Spec(
        None,
        "missing caveat test",
        "serial_status",
        [[T("get_serial", serial_number="SN-0404")]],
        "SN-0404 is in Bay 1.",
        [],
        [],
    ),
    Spec(
        None,
        "repairable output test",
        "serial_status",
        [[T("get_serial", serial_number="SN-0042")]],
        "SN-0042 is IN_BUILD.",
        [("SN-0042 is in build.", [S("SN-0042", "status", "IN_BUILD")])],
        raw=["Sure! SN-0042 is in build."],
    ),
    Spec(
        None,
        "malformed output test",
        "serial_status",
        [[T("get_serial", serial_number="SN-0042")]],
        raw=["Sure!", "Still not JSON."],
    ),
]


def main() -> None:
    from p1_fixtures import P1_GOLDEN, P1_TEST_ONLY

    golden = GOLDEN + P1_GOLDEN
    specs = golden + TEST_ONLY + P1_TEST_ONLY
    # Longer triggers first, so a short trigger never shadows a more specific question.
    ordered = sorted(specs, key=lambda s: -len(s.trigger))
    mock = {
        "router": [{"trigger": s.trigger, "workflow": s.workflow} for s in ordered],
        "workflows": [
            {"id": s.case_id or s.question, "trigger": s.trigger, "steps": s.steps} for s in ordered
        ],
    }
    (ROOT / "fixtures").mkdir(exist_ok=True)
    (ROOT / "fixtures" / "llm-mock.json").write_text(
        json.dumps(mock, indent=1) + "\n", encoding="utf-8"
    )
    by_workflow: dict[str, list[dict[str, Any]]] = {}
    for s in golden:
        assert s.case_id
        by_workflow.setdefault(s.workflow, []).append(
            {
                "id": s.case_id,
                "question": s.question,
                "expected_workflow": s.workflow,
                "expected_decision": s.decision,
                "expected_facts": s.expected_facts(),
                "forbidden_values": [],
            }
        )
    cases_dir = ROOT / "evals" / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    for workflow, cases in by_workflow.items():
        (cases_dir / f"{workflow}.yaml").write_text(
            yaml.safe_dump(cases, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
    print(f"{len(specs)} mock scripts, {len(golden)} golden cases in {len(by_workflow)} files")


if __name__ == "__main__":
    main()
