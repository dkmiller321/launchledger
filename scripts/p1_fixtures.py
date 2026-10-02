"""P1 golden cases and scripts (stage 7): W7-W12, 5 cases each. Values come from the pinned seed
(DW rollups computed by `rebuild_dw` with today = 2026-10-01). Definitions: DECISIONS D14.
"""

from build_fixtures import BL, NCR, PO, WO, F, Spec, T


def REQ(rid: str, field: str, value: object) -> dict[str, object]:
    return F("REQ", "requirement", rid, field, value)


def PART(pn: str, field: str, value: object) -> dict[str, object]:
    return F("PLM", "part", pn, field, value)


def SOT(sid: str, field: str, value: object) -> dict[str, object]:
    return F("DW", "supplier_on_time", sid, field, value)


def CYC(pn: str, field: str, value: object) -> dict[str, object]:
    return F("DW", "wo_cycle_time", pn, field, value)


P1_GOLDEN: list[Spec] = [
    # --- W7 requirement_trace ---------------------------------------------------------------
    Spec(
        "W7-01",
        "Trace requirement REQ-118",
        "requirement_trace",
        [
            [T("get_requirement", req_id="REQ-118")],
            [T("list_requirement_parts", req_id="REQ-118")],
            [T("list_ncrs", requirement_id="REQ-118", status="OPEN")],
        ],
        "REQ-118 (Casting porosity limited to ASTM E505 level 2) applies to P-1077. Two NCRs "
        "are open against it: NCR-0311 on SN-0042 and NCR-0320 on SN-0057.",
        [
            (
                "REQ-118 limits casting porosity.",
                [REQ("REQ-118", "text", "Casting porosity limited to ASTM E505 level 2")],
            ),
            ("It applies to P-1077.", [PART("P-1077", "part_number", "P-1077")]),
            (
                "NCR-0311 and NCR-0320 are open against it.",
                [
                    NCR("NCR-0311", "requirement_id", "REQ-118"),
                    NCR("NCR-0311", "status", "OPEN"),
                    NCR("NCR-0320", "requirement_id", "REQ-118"),
                    NCR("NCR-0320", "status", "OPEN"),
                ],
            ),
        ],
    ),
    Spec(
        "W7-02",
        "Trace requirement REQ-104",
        "requirement_trace",
        [
            [T("get_requirement", req_id="REQ-104")],
            [T("list_requirement_parts", req_id="REQ-104")],
            [T("list_ncrs", requirement_id="REQ-104", status="OPEN")],
        ],
        "REQ-104 (Mounting face finish 63 Ra max) applies to P-2001. No open NCRs are recorded "
        "against it.",
        [
            (
                "REQ-104 sets the mounting face finish.",
                [REQ("REQ-104", "text", "Mounting face finish 63 Ra max")],
            ),
            ("It applies to P-2001.", [PART("P-2001", "part_number", "P-2001")]),
        ],
        ["MES has no open NCRs against REQ-104."],
    ),
    Spec(
        "W7-03",
        "Which parts does REQ-118 apply to?",
        "requirement_trace",
        [[T("list_requirement_parts", req_id="REQ-118")]],
        "REQ-118 applies to one part: P-1077 (Turbopump inducer housing).",
        [
            (
                "REQ-118 applies to P-1077.",
                [
                    PART("P-1077", "part_number", "P-1077"),
                    PART("P-1077", "name", "Turbopump inducer housing"),
                ],
            )
        ],
    ),
    Spec(
        "W7-04",
        "What is the verification method for REQ-104?",
        "requirement_trace",
        [[T("get_requirement", req_id="REQ-104")]],
        "REQ-104 is verified by Inspection.",
        [
            (
                "REQ-104 is verified by inspection.",
                [REQ("REQ-104", "verification_method", "Inspection")],
            )
        ],
    ),
    Spec(
        "W7-05",
        "Trace requirement REQ-999",
        "requirement_trace",
        [[T("get_requirement", req_id="REQ-999")]],
        "I couldn't find REQ-999 in the requirements system.",
        [],
        ["REQ-999 was not found in REQ."],
    ),
    # --- W8 revision_impact -----------------------------------------------------------------
    Spec(
        "W8-01",
        "What's the impact of moving P-1077 to rev D?",
        "revision_impact",
        [
            [T("where_used", part_number="P-1077")],
            [T("get_part", part_number="P-2110")],
            [T("list_work_orders", part_number="P-2001")],
            [T("list_work_orders", part_number="P-2110")],
        ],
        "Moving P-1077 to rev D affects P-2001 and P-2110 builds. Work orders not yet closed: "
        "WO-50102 and WO-50103 on SN-0042, WO-50410 on SN-0120, and WO-50217 on SN-0057.",
        [
            (
                "P-1077 is used in P-2001 and P-2110.",
                [BL("BL-0001", "parent_pn", "P-2001"), BL("BL-0002", "parent_pn", "P-2110")],
            ),
            (
                "SN-0042 has two open work orders.",
                [
                    WO("WO-50102", "serial_number", "SN-0042"),
                    WO("WO-50102", "status", "BLOCKED"),
                    WO("WO-50103", "serial_number", "SN-0042"),
                    WO("WO-50103", "status", "OPEN"),
                ],
            ),
            (
                "SN-0120 and SN-0057 each have one.",
                [
                    WO("WO-50410", "serial_number", "SN-0120"),
                    WO("WO-50410", "status", "OPEN"),
                    WO("WO-50217", "serial_number", "SN-0057"),
                    WO("WO-50217", "status", "OPEN"),
                ],
            ),
        ],
    ),
    Spec(
        "W8-02",
        "What's the impact of moving P-3300 to rev E?",
        "revision_impact",
        [[T("where_used", part_number="P-3300")], [T("list_work_orders", part_number="P-2001")]],
        "Moving P-3300 to rev E affects P-2001 builds: WO-50102 and WO-50103 on SN-0042 and "
        "WO-50410 on SN-0120 are not closed.",
        [
            ("P-3300 is used in P-2001.", [BL("BL-0003", "parent_pn", "P-2001")]),
            (
                "Three P-2001 work orders are not closed.",
                [
                    WO("WO-50102", "status", "BLOCKED"),
                    WO("WO-50103", "status", "OPEN"),
                    WO("WO-50410", "status", "OPEN"),
                ],
            ),
        ],
    ),
    Spec(
        "W8-03",
        "What's the impact of moving P-1500 to rev B?",
        "revision_impact",
        [[T("where_used", part_number="P-1500")]],
        "No assemblies use P-1500, so a revision change has no BOM impact.",
        [],
        ["PLM lists no BOM lines that use P-1500."],
    ),
    Spec(
        "W8-04",
        "Which open work orders build P-2110?",
        "revision_impact",
        [[T("list_work_orders", part_number="P-2110")]],
        "One open work order builds P-2110: WO-50217 on SN-0057.",
        [
            (
                "WO-50217 on SN-0057 is open.",
                [WO("WO-50217", "serial_number", "SN-0057"), WO("WO-50217", "status", "OPEN")],
            )
        ],
    ),
    Spec(
        "W8-05",
        "What's the impact of moving P-9999 to rev B?",
        "revision_impact",
        [[T("where_used", part_number="P-9999")]],
        "I couldn't find part P-9999 in PLM.",
        [],
        ["P-9999 was not found in PLM."],
    ),
    # --- W9 supplier_scorecard --------------------------------------------------------------
    Spec(
        "W9-01",
        "Show the scorecard for Apex Castings",
        "supplier_scorecard",
        [
            [T("find_supplier", name="Apex Castings")],
            [T("dw_supplier_on_time", supplier_id="SUP-007")],
            [T("list_pos", supplier_id="SUP-007", late_only=True)],
        ],
        "Apex Castings: on-time rate 100% (1 of 1 received POs on time), with 1 open late PO: "
        "PO-10233.",
        [
            (
                "Apex Castings delivered 1 of 1 received POs on time.",
                [
                    SOT("SUP-007", "on_time_rate", 1.0),
                    SOT("SUP-007", "pos_received", 1),
                    SOT("SUP-007", "pos_on_time", 1),
                ],
            ),
            (
                "PO-10233 is its one open late PO.",
                [SOT("SUP-007", "open_late_pos", 1), PO("PO-10233", "status", "OPEN")],
            ),
        ],
    ),
    Spec(
        "W9-02",
        "Show the scorecard for Cryo Valve Works",
        "supplier_scorecard",
        [
            [T("find_supplier", name="Cryo Valve Works")],
            [T("dw_supplier_on_time", supplier_id="SUP-019")],
            [T("list_pos", supplier_id="SUP-019", late_only=True)],
        ],
        "Cryo Valve Works has no received POs yet, so it has no on-time history; 1 open PO is "
        "late: PO-10410.",
        [
            ("No received POs yet.", [SOT("SUP-019", "pos_received", 0)]),
            (
                "PO-10410 is late.",
                [SOT("SUP-019", "open_late_pos", 1), PO("PO-10410", "status", "OPEN")],
            ),
        ],
    ),
    Spec(
        "W9-03",
        "Show the scorecard for Orbital Fasteners",
        "supplier_scorecard",
        [
            [T("find_supplier", name="Orbital Fasteners")],
            [T("dw_supplier_on_time", supplier_id="SUP-012")],
            [T("list_pos", supplier_id="SUP-012", late_only=True)],
        ],
        "Orbital Fasteners has no received POs and no late open POs.",
        [
            (
                "No received or late POs.",
                [SOT("SUP-012", "pos_received", 0), SOT("SUP-012", "open_late_pos", 0)],
            )
        ],
        ["ERP returned no late POs for Orbital Fasteners."],
    ),
    Spec(
        "W9-04",
        "How many open late POs does Apex Castings have?",
        "supplier_scorecard",
        [
            [T("find_supplier", name="Apex Castings")],
            [T("dw_supplier_on_time", supplier_id="SUP-007")],
        ],
        "Apex Castings has 1 open late PO.",
        [("One open late PO.", [SOT("SUP-007", "open_late_pos", 1)])],
    ),
    Spec(
        "W9-05",
        "Show the scorecard for Acme Rockets",
        "supplier_scorecard",
        [[T("find_supplier", name="Acme Rockets")]],
        "No supplier named Acme Rockets was found in ERP.",
        [],
        ["No supplier named Acme Rockets was found in ERP."],
    ),
    # --- W10 cycle_time ---------------------------------------------------------------------
    Spec(
        "W10-01",
        "What's the cycle time for P-2001?",
        "cycle_time",
        [[T("dw_cycle_time", part_number="P-2001")]],
        "P-2001 work orders take 17.0 days on average (1 closed work order; the latest took "
        "17.0 days).",
        [
            (
                "Average and latest cycle time are 17 days.",
                [
                    CYC("P-2001", "avg_cycle_days", 17.0),
                    CYC("P-2001", "last_cycle_days", 17.0),
                    CYC("P-2001", "closed_wos", 1),
                ],
            )
        ],
    ),
    Spec(
        "W10-02",
        "What's the cycle time for P-1500?",
        "cycle_time",
        [[T("dw_cycle_time", part_number="P-1500")]],
        "P-1500 work orders take 24.0 days on average (1 closed work order).",
        [
            (
                "Average cycle time is 24 days.",
                [CYC("P-1500", "avg_cycle_days", 24.0), CYC("P-1500", "closed_wos", 1)],
            )
        ],
    ),
    Spec(
        "W10-03",
        "What's the cycle time for P-2110?",
        "cycle_time",
        [[T("dw_cycle_time", part_number="P-2110")]],
        "There is no cycle-time history for P-2110 yet.",
        [],
        ["The data warehouse has no closed work orders for P-2110."],
    ),
    Spec(
        "W10-04",
        "How many closed work orders does P-2001 have?",
        "cycle_time",
        [[T("dw_cycle_time", part_number="P-2001")]],
        "P-2001 has 1 closed work order in the data warehouse.",
        [("One closed work order.", [CYC("P-2001", "closed_wos", 1)])],
    ),
    Spec(
        "W10-05",
        "What's the cycle time for P-9999?",
        "cycle_time",
        [[T("dw_cycle_time", part_number="P-9999")]],
        "I couldn't find cycle-time data for P-9999.",
        [],
        ["P-9999 has no cycle-time record in the data warehouse."],
    ),
    # --- W11 shortage_report ----------------------------------------------------------------
    Spec(
        "W11-01",
        "Shortage report for P-1077",
        "shortage_report",
        [
            [T("where_used", part_number="P-1077")],
            [T("list_work_orders", part_number="P-2001")],
            [T("list_work_orders", part_number="P-2110")],
            [T("list_pos", part_number="P-1077", status="OPEN")],
        ],
        "P-1077 is covered: open demand is 3 units (SN-0042, SN-0120, SN-0057) against 6 on "
        "order (PO-10233 for 4, which is late, and PO-10240 for 2).",
        [
            (
                "Demand comes from three serials with open work orders.",
                [
                    BL("BL-0001", "qty", 1),
                    BL("BL-0002", "qty", 1),
                    WO("WO-50102", "serial_number", "SN-0042"),
                    WO("WO-50410", "serial_number", "SN-0120"),
                    WO("WO-50217", "serial_number", "SN-0057"),
                ],
            ),
            ("Six units are on order.", [PO("PO-10233", "qty", 4), PO("PO-10240", "qty", 2)]),
        ],
    ),
    Spec(
        "W11-02",
        "Shortage report for P-3300",
        "shortage_report",
        [
            [T("where_used", part_number="P-3300")],
            [T("list_work_orders", part_number="P-2001")],
            [T("list_pos", part_number="P-3300", status="OPEN")],
        ],
        "P-3300 is covered: demand is 2 units (SN-0042, SN-0120) against 15 on order (PO-10300 "
        "for 10, and PO-10410 for 5, which is late).",
        [
            (
                "Demand comes from two P-2001 serials.",
                [
                    BL("BL-0003", "qty", 1),
                    WO("WO-50102", "serial_number", "SN-0042"),
                    WO("WO-50410", "serial_number", "SN-0120"),
                ],
            ),
            ("Fifteen units are on order.", [PO("PO-10300", "qty", 10), PO("PO-10410", "qty", 5)]),
        ],
    ),
    Spec(
        "W11-03",
        "Shortage report for P-1500",
        "shortage_report",
        [[T("where_used", part_number="P-1500")]],
        "No assemblies use P-1500, so there is no build demand for it.",
        [],
        ["PLM lists no BOM lines that use P-1500."],
    ),
    Spec(
        "W11-04",
        "How many P-1077 are on order?",
        "shortage_report",
        [[T("list_pos", part_number="P-1077", status="OPEN")]],
        "6 units of P-1077 are on order: PO-10233 for 4 and PO-10240 for 2.",
        [("Six units on two open POs.", [PO("PO-10233", "qty", 4), PO("PO-10240", "qty", 2)])],
    ),
    Spec(
        "W11-05",
        "Shortage report for P-9999",
        "shortage_report",
        [[T("where_used", part_number="P-9999")]],
        "I couldn't find part P-9999 in PLM.",
        [],
        ["P-9999 was not found in PLM."],
    ),
    # --- W12 export_check -------------------------------------------------------------------
    Spec(
        "W12-01",
        "Which export-controlled parts are in P-2001?",
        "export_check",
        [
            [T("get_bom", part_number="P-2001")],
            [T("get_part", part_number="P-1077")],
            [T("get_part", part_number="P-3300")],
        ],
        "P-2001 contains one export-controlled part: P-1077 (Turbopump inducer housing). "
        "P-3300 is not export-controlled.",
        [
            (
                "P-1077 is export-controlled.",
                [
                    PART("P-1077", "export_controlled", True),
                    PART("P-1077", "name", "Turbopump inducer housing"),
                ],
            ),
            ("P-3300 is not.", [PART("P-3300", "export_controlled", False)]),
        ],
    ),
    Spec(
        "W12-02",
        "Which export-controlled parts are in P-2110?",
        "export_check",
        [[T("get_bom", part_number="P-2110")], [T("get_part", part_number="P-1077")]],
        "P-2110 contains one export-controlled part: P-1077 (Turbopump inducer housing).",
        [
            (
                "P-1077 is in P-2110 and export-controlled.",
                [BL("BL-0002", "child_pn", "P-1077"), PART("P-1077", "export_controlled", True)],
            )
        ],
    ),
    Spec(
        "W12-03",
        "Is P-3300 export-controlled?",
        "export_check",
        [[T("get_part", part_number="P-3300")]],
        "No. P-3300 (Engine controller harness) is not export-controlled.",
        [
            (
                "P-3300 is not export-controlled.",
                [
                    PART("P-3300", "export_controlled", False),
                    PART("P-3300", "name", "Engine controller harness"),
                ],
            )
        ],
    ),
    Spec(
        "W12-04",
        "Is P-1077 export-controlled?",
        "export_check",
        [[T("get_part", part_number="P-1077")]],
        "Yes. P-1077 (Turbopump inducer housing) is export-controlled.",
        [
            (
                "P-1077 is export-controlled.",
                [
                    PART("P-1077", "export_controlled", True),
                    PART("P-1077", "name", "Turbopump inducer housing"),
                ],
            )
        ],
    ),
    Spec(
        "W12-05",
        "Which export-controlled parts are in P-1500?",
        "export_check",
        [[T("get_bom", part_number="P-1500")]],
        "P-1500 has no child parts in PLM, so it contains no export-controlled parts.",
        [],
        ["PLM lists no BOM lines under P-1500."],
    ),
]

P1_TEST_ONLY: list[Spec] = []
