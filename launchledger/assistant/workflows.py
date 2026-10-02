"""Workflows: one tool-calling agent each, with its own prompt and allowed tools (PRD A2, W)."""

from dataclasses import dataclass

MAX_TOOL_CALLS = 8


@dataclass(frozen=True)
class Workflow:
    id: str  # W1..W12
    name: str
    description: str
    tools: tuple[str, ...]
    guidance: str
    priority: str = "P0"


WORKFLOWS: dict[str, Workflow] = {
    w.name: w
    for w in (
        Workflow(
            "W1",
            "serial_status",
            "Where a serial is, its status, and what blocks it.",
            ("get_serial", "list_work_orders", "get_part"),
            "Report the serial's status and location, then any BLOCKED or OPEN work "
            "orders and what they wait on.",
        ),
        Workflow(
            "W2",
            "supplier_impact",
            "Open work orders at risk from a supplier's late purchase orders.",
            ("find_supplier", "get_supplier", "list_pos", "list_work_orders"),
            "Find the supplier, list its OPEN POs, decide which are late (an OPEN PO is "
            "late if promised_date is after due_date or due_date is before today), then "
            "list work orders whose depends_on_po is a late PO.",
        ),
        Workflow(
            "W3",
            "where_used",
            "Which assemblies use a part, or what an assembly contains.",
            ("where_used", "get_bom", "get_part"),
            "Use where_used for 'which assemblies use X' and get_bom for 'what is in X'.",
        ),
        Workflow(
            "W4",
            "ncr_summary",
            "Nonconformances against a serial or part.",
            ("list_ncrs", "get_serial", "get_part"),
            "List the NCRs with severity, status, description and requirement.",
        ),
        Workflow(
            "W5",
            "po_status",
            "Status of a purchase order and whether it is late.",
            ("get_po", "get_supplier", "list_work_orders"),
            "Report status, due and promised dates, the supplier name, and whether it is "
            "late (OPEN and promised after due, or due before today).",
        ),
        Workflow(
            "W6",
            "build_readiness",
            "Whether a serial is ready for integration.",
            ("get_serial", "list_work_orders", "list_inspections", "list_ncrs"),
            "Ready only if every work order is CLOSED, inspections passed and no NCR is "
            "OPEN. Start the answer with 'Yes.' or 'No.'.",
        ),
        Workflow(
            "W7",
            "requirement_trace",
            "Requirement to parts to open NCRs.",
            ("get_requirement", "list_requirement_parts", "list_ncrs"),
            "Get the requirement, the parts it applies to, and open NCRs against it.",
            "P1",
        ),
        Workflow(
            "W8",
            "revision_impact",
            "Serials and open work orders affected if a part changes revision.",
            ("where_used", "get_part", "list_work_orders"),
            "Find assemblies using the part, then their serials' open work orders.",
            "P1",
        ),
        Workflow(
            "W9",
            "supplier_scorecard",
            "A supplier's on-time rate and open late POs.",
            ("find_supplier", "dw_supplier_on_time", "list_pos"),
            "Report the on-time rate from the data warehouse and list open late POs.",
            "P1",
        ),
        Workflow(
            "W10",
            "cycle_time",
            "Work-order cycle time for a part.",
            ("dw_cycle_time", "get_part"),
            "Report the average and latest cycle time in days.",
            "P1",
        ),
        Workflow(
            "W11",
            "shortage_report",
            "Whether open POs cover the open work-order demand for a part.",
            ("get_part", "list_pos", "list_work_orders", "where_used"),
            "Demand = open work orders on serials of assemblies that use the part; supply "
            "= open PO quantity for the part.",
            "P1",
        ),
        Workflow(
            "W12",
            "export_check",
            "Which parts in an assembly are export-controlled.",
            ("get_bom", "get_part"),
            "Name the export-controlled parts by number and name only. Never reveal any "
            "other field of an export-controlled part.",
            "P1",
        ),
    )
}

WORKFLOW_BY_ID = {w.id: w for w in WORKFLOWS.values()}

OUTPUT_RULES = """\
Answer ONLY from tool results. When you are done calling tools, reply with ONE JSON object and
nothing else:
{"answer": "<plain-English answer>",
 "claims": [{"text": "<one claim>", "facts": [{"system": "MES", "record_type": "work_order",
   "record_id": "WO-50102", "field": "status", "value": "BLOCKED"}]}],
 "caveats": ["<anything you could not verify>"]}
Rules: every claim needs at least one fact; each fact cites one field of one record exactly as
the tool returned it (system is PLM, MES, ERP, REQ or DW; record_type is the record's type, e.g.
serial, work_order, inspection, ncr, part, bom_line, purchase_order, supplier, requirement,
supplier_on_time, wo_cycle_time). If a tool returns not_found or no items, say so in caveats.
Never reveal controlled_notes or any field of an export-controlled part other than its
part_number and name. Today is {today}."""


def system_prompt(workflow: Workflow, today: str) -> str:
    return (
        f"You are LaunchLedger, an assistant for Halcyon Aerospace's manufacturing, quality "
        f"and supply-chain systems. Workflow: {workflow.name}: {workflow.description} "
        f"{workflow.guidance}\n\n" + OUTPUT_RULES.replace("{today}", today)
    )


def router_tool() -> dict[str, object]:
    names = [*WORKFLOWS.keys(), "unsupported"]
    described = "; ".join(f"{w.name}: {w.description}" for w in WORKFLOWS.values())
    return {
        "type": "function",
        "function": {
            "name": "select_workflow",
            "description": "Pick the workflow that answers the question, or unsupported. "
            + described,
            "parameters": {
                "type": "object",
                "required": ["workflow"],
                "properties": {"workflow": {"type": "string", "enum": names}},
            },
        },
    }


ROUTER_PROMPT = (
    "Route the user's question about Halcyon Aerospace's manufacturing systems to "
    "exactly one workflow by calling select_workflow. Use unsupported when no "
    "workflow fits."
)
